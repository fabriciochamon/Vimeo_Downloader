import json, re, uuid, requests, shutil, os, time
from multiprocessing import Pool, Pipe
from playwright.sync_api import sync_playwright, Playwright, expect
import dearpygui.dearpygui as dpg
from pprint import pprint

headless_mode       = True              # playwright headless ?
worker_num          = 6                 # max parallel browser windows allowed
worker_timeout      = 5                 # borwser page timeouts
download_chunk_size = 30 * (1024*1024)  # 30 Mb

# cleans string for folder names on windows
def clean_chars(filename):
	keepcharacters = (' ','.','_','-')
	return "".join(c for c in filename if c.isalnum() or c in keepcharacters).rstrip()

# log to ui widget or Pipe connection, if provided
def log(msg, conn=None):
	if conn: conn.send(msg)
	else: dpg.set_value('status', msg)

# download video thumbnails
def download_image(url, name):
	os.makedirs('cache', exist_ok=True)
	destination = f'./cache/{name}.jpg'
	response = requests.get(url, stream=True)
	if response and response.status_code == 200:
		with open(destination, 'wb') as out_file:
			response.raw.decode_content = True
			shutil.copyfileobj(response.raw, out_file)
		del response

# download video file to disk
def download_video(video, fmt, path, chunk_size, conn):
	response = requests.get(fmt['url'], stream=True)

	# check response
	if response and response.status_code == 200:
		filename = response.headers['Content-Disposition'].split(';')
		filename = [item.strip() for item in filename if item.strip().startswith('filename=')][0]
		filename = filename.split('=')[1]
		filename = filename.replace('\"', '').strip()

		# make destination path
		destination = os.path.join(path, filename)
		destination = destination.replace('\\', '/')
		os.makedirs(os.path.dirname(destination), exist_ok=True)

		total_size = int(response.headers['content-length'])
		total_downloaded = 0

		# if file already exists, skip
		if os.path.isfile(destination):
			del response
			if conn: 
				dl_status={
					'video': video,
					'size': total_size,
					'fmt': fmt,
					'progress': 1,
				}
				conn.send(dl_status)
			return

		def clamp(val, minval, maxval):
		    if val < minval: return minval
		    if val > maxval: return maxval
		    return val

	    # otherwise, download file to disk
		with open(destination, 'wb') as out_file:
			for chunk in response.iter_content(chunk_size=chunk_size):
				if chunk:
					out_file.write(chunk)
					total_downloaded+=chunk_size
					if conn: 
						dl_status={
							'video': video,
							'size': total_size,
							'fmt': fmt,
							'progress': clamp(float(total_downloaded)/total_size, 0, 1),
						}
						conn.send(dl_status)

		# send final progress state through conn
		if conn: 
			dl_status={
				'video': video,
				'size': total_size,
				'fmt': fmt,
				'progress': 1,
			}
			conn.send(dl_status)
		
		del response

# set ui widgets progress (expects "progress" as a normalized value)
def set_progress_bar(progress, video_id=None):
	tag='fetch_progress'
	if video_id: tag+=f'_{video_id}'
	dpg.set_value(tag, progress)
	if not video_id: dpg.configure_item(tag, overlay=f'{int(progress*100)} %')

# init playwright
def init_pw():	
	global headless_mode, worker_timeout

	pw = sync_playwright().start()
	browser = pw.chromium.launch(headless=headless_mode)
	context = browser.new_context(
		viewport={
			'width':  1280, 
			'height': 720,
			},
		locale='en-US',
	)
	context.set_default_timeout(worker_timeout*60*1000)
	page = context.new_page()

	# get credentials
	credentials = None
	with open('credentials.json', 'r') as f:
		credentials = json.load(f)

	ret = {
		'pw': pw,
		'page': page,
		'browser': browser,
		'context': context,
		'credentials': credentials,
		'vimeo_username': None,
	}

	return ret

# close playwright
def terminate_pw(pwt):
	pwt['context'].close()
	pwt['browser'].close()
	pwt['pw'].stop()


# vimeo login
def login(pwt=None, terminate=False, conn=None):
	vimeo_username = None

	pw = pwt or init_pw()
	page = pw['page']
	credentials = pw['credentials']

	if pw['vimeo_username'] is None:
		
		if credentials:
			user = credentials['username']
			pwd  = credentials['password']
			page.goto('https://vimeo.com/')
			page.get_by_role("button", name="Log In").click()
			page.locator("#modal-root iframe").content_frame.get_by_test_id("site_login_email_input").fill(user)
			page.locator("#modal-root iframe").content_frame.get_by_test_id("site_login_password_input").fill(pwd)
			page.locator("#modal-root iframe").content_frame.get_by_test_id("site_login_submit_button").click()
			page.get_by_role('button', name='avatar button').click()
			page.get_by_role('link', name='View profile').click()
			vimeo_username = page.url.split('/')[-1]
			pw['vimeo_username'] = vimeo_username			

	if terminate: terminate_pw(pw)

	return pw

# get pagination data from user's channel
def get_num_video_pages(pwt=None, terminate=False):

	# init playwright
	pw = pwt or init_pw()
	page = pw['page']
	credentials = pw['credentials']

	npages = None

	# login
	pw = login(pw)
	vimeo_username = pw['vimeo_username']

	# get pagination
	log('Fetching video pagination...')
	page.goto(f"https://vimeo.com/{vimeo_username}/videos")
	pagination = page.locator('id=pagination').get_by_role('listitem').all_text_contents()
	pagination = [item.replace('\n', '').strip() for item in pagination]
	npages = pagination[-1] if 'Next' not in pagination else pagination[-2]
	npages = int(npages)
	
	if terminate: terminate_pw(pw)

	return npages

# get video list from specific page
def get_videos_from_page(pwt=None, page_number=1, terminate=False, conn=None):

	videos = []
	
	# init playwright
	pw = pwt or init_pw()
	page = pw['page']
	credentials = pw['credentials']

	# login
	pw = login(pw, conn=conn)
	vimeo_username = pw['vimeo_username']

	# goto page number requested
	curpage = page_number
	if conn: conn.send(f'Fetching video list (Page {curpage})...')
	page.goto(f"https://vimeo.com/{vimeo_username}/videos/page:{curpage}/sort:date")

	# get video list from page
	video_items = page.locator("id=browse_content").nth(1).get_by_role('list').nth(0).get_by_role('listitem').all()
	i=0
	for item in video_items:
		video = {}
		i+=1
		if conn: conn.send(f'Fetching video list (Page {curpage}) - video {i}...')
		
		# check if video is really available (sometimes can contain empty data)
		# for example when user removed video
		texts = item.all_text_contents()
		texts = ''.join([x.strip().replace('\n','') for x in texts]).strip()
		texts = re.sub(r'\s{2,}', ' ', texts)
		video_available = texts != ''

		# fetch url, title ad thumbnail for each video
		if video_available:
			url_src = item.get_by_role('link').nth(0).get_attribute('href')
			url = f'http://vimeo.com{url_src}'
			url_manage = f'http://vimeo.com/manage/videos{url_src}'
			title = item.get_by_role('link').nth(0).get_attribute('title')
			video_id = str(uuid.uuid1())
			video['id'] = video_id
			video['thumb'] = item.get_by_role('link').nth(0).locator('[class="thumbnail thumbnail_lg_wide"]').get_attribute('src')
			if conn: conn.send(f'Fetching video list (Page {curpage}) - video {i} (thumbnail)...')
			download_image(video['thumb'], video_id)
			video['url'] = url
			video['url_manage'] = url_manage
			video['title'] = title
			videos.append(video)

	if terminate: terminate_pw(pw)

	return videos

# get video download formats available (1080p, 720p, original resolution, etc)
def get_download_formats_from_video(pwt=None, video=None, terminate=False, conn=None):
	
	# init playwright
	pw = pwt or init_pw()
	page = pw['page']
	credentials = pw['credentials']

	# login
	pw = login(pw, conn=conn)
	vimeo_username = pw['vimeo_username']

	# get formats
	if conn: conn.send(f'Fetching video formats for video: \"{video["title"]}\"')
	page.goto(video['url_manage'])
	page.locator('[aria-label="More sharing options"]').click()
	page.get_by_text("Download...").locator('xpath=..').click()
	format_items = page.locator('[id^="download-file-"]').all()
	formats = []

	for item in format_items:

		data = item.all_inner_texts()[0]
		data = data.split('\n\n')
		data = [x for x in data if x.strip() != '|']
		url = item.get_by_role('link').first.get_attribute('href')
		
		fmt = {
			'title': data[0],
			'video_size': data[1],
			'resolution': data[2],
			'url' : item.get_by_role('link').first.get_attribute('href'),
		}
		formats.append(fmt)

	if terminate: terminate_pw(pw)

	video['formats'] = formats

	return video

# track workers for video list fetch process
def track_workers(results, conn):
	last_msg = ''
	while True:		
		has_msg = conn.poll(0)
		all_items_ready = all([result.ready() for result in results])
		items_ready = sum([result.ready() for result in results])
		num_items = len(results)
		if has_msg: 
			last_msg = conn.recv()
			has_msg = False
		log(f'[{items_ready} of {num_items}] {last_msg}')
		progress = float(items_ready)/num_items
		set_progress_bar(progress)
		if all_items_ready: break
		time.sleep(0.2)

# ui logic to update video download progress bars and themes
def update_video_progress(dl_status, downloads):
	item_tag = f'dl@@{dl_status["video"]["id"]}@@{dl_status["fmt"]["title"]}'
	dpg.set_item_user_data(item_tag, dl_status['progress'])
	video_id = dl_status["video"]["id"]
	download_formats = downloads[video_id]	
	total_progress = sum([dpg.get_item_user_data(f'dl@@{video_id}@@{fmt['title']}') or 0 for fmt in download_formats])
	total_progress = float(total_progress)/len(download_formats)
	set_progress_bar(total_progress, video_id)
	if total_progress>=1:
		dpg.bind_item_theme(f'fetch_progress_{video_id}', 'finished_download')
	if dl_status['progress']>=1:
		dpg.bind_item_theme(item_tag, 'finished_download')

# track workers for video downloads
def track_download_workers(results, downloads, conn):
	last_msg = ''
	while True:		
		has_msg = conn.poll(0)
		all_items_ready = all([result.ready() for result in results])
		items_ready = sum([result.ready() for result in results])
		num_items = len(results)
		if has_msg: 
			last_msg = conn.recv()
			has_msg = False
		dl_status = last_msg
		if dl_status:
			log(f'Downloading video {items_ready} of {num_items}')
			dpg.configure_item(f'dl@@{dl_status["video"]["id"]}@@{dl_status["fmt"]["title"]}', user_data=dl_status['progress'])
			update_video_progress(dl_status, downloads)
			set_progress_bar(float(items_ready)/num_items) # overall process
		if all_items_ready: break
		time.sleep(0.2)


# ---------------- MAIN PROCESSES ---------------- #

# fetch all videos from user channel
def get_all_user_videos():

	dpg.show_item('loading')

	# user cached data if present
	if os.path.isfile('cache.json'):
		with open('cache.json', 'r') as f:
			videos = json.load(f)
	
	# otherwise scrape data using playwright
	else:

		global worker_num, worker_timeout
		log(f'initializing with {worker_num} workers (worker timeout = {worker_timeout} min)...')
		
		proc_count = worker_num
		parent_conn, child_conn = Pipe()
		pool = Pool(proc_count)
		
		# get video list
		results = []
		npages = get_num_video_pages(terminate=True)
		for page_number in range(1, npages+1):
			args = {
				'pwt': None, 
				'page_number': page_number, 
				'terminate': True,
				'conn': child_conn,
			}
			result = pool.apply_async(get_videos_from_page, kwds=args)
			results.append(result)
		
		track_workers(results, parent_conn)
		videos = sum([result.get() for result in results], [])

		# get download formats
		results = []
		for video in videos:
			args = {
				'pwt': None, 
				'video': video, 
				'terminate': True,
				'conn': child_conn,
			}
			result = pool.apply_async(get_download_formats_from_video, kwds=args)
			results.append(result)
		
		track_workers(results, parent_conn)
		videos = [result.get() for result in results]

		# close pipe connection
		child_conn.close()	

		# cache results
		with open('cache.json', 'w') as f:
			json.dump(videos, f, indent=4)

	log(f'Done fetching {len(videos)} videos.')	
	set_progress_bar(1)
	dpg.hide_item('loading')
	
	return videos

# download all selected videos
def download_videos(videos, downloads):
	
	global worker_num, worker_timeout, download_chunk_size

	dpg.show_item('loading')
	log(f'Starting downloads...')

	proc_count = worker_num
	parent_conn, child_conn = Pipe()
	pool = Pool(proc_count)

	results = []
	for video_id, download_formats in downloads.items():
		video = [video for video in videos if video['id']==video_id][0]
		dpg.show_item(f'fetch_progress_{video["id"]}')
		base_dir = './downloads'
		for fmt in download_formats:
			path = os.path.join(base_dir, clean_chars(video['title'])).replace('\\', '/')
			args = {
				'video': video, 
				'fmt': fmt, 
				'path': path, 
				'chunk_size': download_chunk_size,
				'conn': child_conn,
			}

			result = pool.apply_async(download_video, kwds=args)
			results.append(result)

	track_download_workers(results, downloads, parent_conn)

	log(f'Finished downloading {len(results)} videos.')

	dpg.hide_item('loading')

# ---------------- MAIN PROCESSES ---------------- #		