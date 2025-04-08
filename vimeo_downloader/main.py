import dearpygui.dearpygui as dpg
import playwright_utils as vimeo
import webbrowser

# CALLBACKS
def set_worker_num(sender, app_data, user_data):
	vimeo.worker_num = app_data

def set_worker_timeout(sender, app_data, user_data):
	vimeo.worker_timeout = app_data

def open_link(sender, app_data, user_data):
	webbrowser.open(user_data)

def select_dl_format(sender, checked, videos):
	selected_fmt = dpg.get_item_label(sender)
	for video in videos:

		# get min/max
		formats = [fmt['title'].replace('p','') for fmt in video['formats']]
		formats = list(set(formats))
		try: formats.remove('Original')
		except: pass
		formats = sorted([int(item) for item in formats])
		smallest = str(formats[0])+'p'
		largest = str(formats[-1])+'p'

		for fmt in video['formats']:
			tag = f'dl@@{video["id"]}@@{fmt["title"]}'
			label = dpg.get_item_label(tag)

			visible = False
			video_search_input = dpg.get_value('video_search_input').split(',')
			for term in video_search_input:
				if term.startswith('-'):
					term = term[1:]
					if term.lower() in video['title'].lower():
						visible=False
						break
				else:
					if term.lower() in video['title'].lower():
						visible=True

			if visible:

				# handle "All"
				if selected_fmt=='All':
					dpg.set_value(tag, checked)

				# handle "Original"
				if selected_fmt=='Original':
					if 'Original' in label:
						dpg.set_value(tag, checked)

				# handle converted formats
				if selected_fmt.replace('p', '').isdigit():
					if selected_fmt in label:
						dpg.set_value(tag, checked)

				# handle largest
				if selected_fmt=='Largest':
					if largest in label and 'Original' not in label:
						dpg.set_value(tag, checked)

				# handle smallest
				if selected_fmt=='Smallest':
					if smallest in label and 'Original' not in label:
						dpg.set_value(tag, checked)


def search_video(sender, app_data):
	dpg.set_value('video_filter', app_data)

def get_user_video_list(sender):
	videos = vimeo.get_all_user_videos()
	dpg.show_item('button_download_selected')
	parent = 'video_list'
	thumb_size_h = 100

	# # search bar and format selection presets
	with dpg.group(parent=parent, horizontal=True, indent=10):
		with dpg.group(horizontal=True):
			dpg.add_text('Search: ')
			dpg.bind_item_font(dpg.last_item(), 'font_small')
			dpg.add_input_text(tag='video_search_input', hint='Video name...', width=200, user_data='main_video_table', callback=lambda s, a, u: dpg.set_value(u, dpg.get_value(s)))
			dpg.bind_item_font(dpg.last_item(), 'font_small')
			dpg.add_spacer(width=20)
			dpg.add_text('Download:   ')
			dpg.bind_item_font(dpg.last_item(), 'font_small')
			dpg.add_checkbox(tag=f'act_dl_all', label='All', callback=select_dl_format, user_data=videos)
			dpg.bind_item_font(dpg.last_item(), 'font_small')
			dpg.add_spacer(width=20)
			formats = [fmt['title'].replace('p','') for video in videos for fmt in video['formats']]
			formats = list(set(formats))
			formats.remove('Original')
			formats = sorted([int(item) for item in formats], reverse=True)
			formats = [str(item)+'p' for item in formats]
			formats.insert(0, 'Original')

			for fmt in formats:
				dpg.add_checkbox(tag=f'act_dl_grp_{fmt}', label=fmt, callback=select_dl_format, user_data=videos)
				dpg.bind_item_font(dpg.last_item(), 'font_small')

			dpg.add_spacer(width=20)
			dpg.add_checkbox(tag=f'act_dl_largest_not_original', label='Largest', callback=select_dl_format, user_data=videos)
			dpg.bind_item_font(dpg.last_item(), 'font_small')

			dpg.add_checkbox(tag=f'act_dl_smallest', label='Smallest', callback=select_dl_format, user_data=videos)
			dpg.bind_item_font(dpg.last_item(), 'font_small')

	dpg.add_separator(parent=parent)
	dpg.add_spacer(parent=parent, height=8)

	with dpg.child_window(parent=parent, border=False, height=-50):

		# build video list table
		with dpg.table(header_row=False, tag='main_video_table', row_background=True):
			dpg.add_table_column(width=thumb_size_h*1.02, width_fixed=True)
			dpg.add_table_column()
			for i, video in enumerate(videos):
				with dpg.table_row(filter_key=video['title']):

					# thumb
					with dpg.table_cell():
						w, h, _, data = dpg.load_image(f'cache/{video["id"]}.jpg')
						thumbnail = dpg.add_static_texture(w, h, data, parent='texreg')
						dpg.add_image(thumbnail, width=thumb_size_h, height=thumb_size_h/(16/9))
						dpg.add_progress_bar(tag=f'fetch_progress_{video["id"]}', height=6, width=thumb_size_h, show=False)
						dpg.bind_item_font(dpg.last_item(), 'font_small')
						dpg.bind_item_theme(dpg.last_item(), 'video_progress_bar')

					# title and dl formats
					with dpg.table_cell():
						with dpg.group():
							video_title = dpg.add_button(label=video['title'], callback=open_link, user_data=video['url'])
							with dpg.tooltip(parent=dpg.last_item(), delay=0.6):
								dpg.add_text('Click to open video page on the browser')
							dpg.bind_item_theme(video_title, 'hyperlink_theme')
							dpg.bind_item_font(video_title, 'font_video_title')
							with dpg.group(horizontal=True):
								formats = sorted(video['formats'], reverse=True, key=lambda d: float(''.join([c for c in d['video_size'] if c.isdigit() or c=='.'])))
								for fmt in formats:
									fmt_label = f'{fmt["title"]} ({fmt["video_size"]})'
									if 'original' in fmt['title'].lower():
										fmt_label = f'{fmt["title"]}: {fmt["resolution"]} ({fmt["video_size"]})'
									dpg.add_checkbox(tag=f'dl@@{video["id"]}@@{fmt["title"]}', label=fmt_label.center(30), user_data=None)
									dpg.bind_item_font(dpg.last_item(), 'font_video_formats')
							dpg.add_spacer(height=10)

		dpg.bind_item_theme('main_video_table', 'video_list_table')


# get all checkbox values for all videos and call download func
def download_selected_videos():
	
	def video_remove_formats(video):
		del video['formats']
		return video

	videos = vimeo.get_all_user_videos()
	downloads = {}
	for video in videos:
		for fmt in video['formats']:
			if dpg.get_value(f'dl@@{video["id"]}@@{fmt["title"]}'):
				if video['id'] not in downloads.keys(): 
					downloads[video['id']] = []
				downloads[video['id']].append(fmt)
				
	vimeo.download_videos(videos, downloads)

# main DPG thread (for multiprocessing)
def main_process():

	# DPG INIT
	dpg.create_context()
	dpg.add_texture_registry(tag='texreg')
	dpg.create_viewport(title='Vimeo Downloader', width=1280, height=720)

	# themes
	with dpg.theme() as global_theme:
		with dpg.theme_component(dpg.mvAll):
			dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
		with dpg.theme_component(dpg.mvCheckbox):
			dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (127, 252, 3))
			dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (127, 252, 3))
	dpg.bind_theme(global_theme)

	with dpg.theme(tag='finished_download'):
		with dpg.theme_component(dpg.mvAll):
			dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (230, 0, 255))
			dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram, (230, 0, 255))

	with dpg.theme(tag='hyperlink_theme'):
		with dpg.theme_component(dpg.mvButton):
			dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
			dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0))
			dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (29, 151, 236, 25))
			dpg.add_theme_color(dpg.mvThemeCol_Text, (29, 151, 236))

	with dpg.theme(tag='download_button_theme'):
		with dpg.theme_component(dpg.mvButton):
			dpg.add_theme_color(dpg.mvThemeCol_Button, (127, 252, 3))
			dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (187, 255, 63))
			dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (187, 255, 63))
			dpg.add_theme_color(dpg.mvThemeCol_Text, (0,0,0))

	with dpg.theme(tag='app_progress_bar'):
		with dpg.theme_component(dpg.mvAll):	
			dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 12)

	with dpg.theme(tag='video_progress_bar'):
		with dpg.theme_component(dpg.mvAll):
			dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram, (127, 252, 3))
			dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (196, 196, 196))
			dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 12)
			
	with dpg.theme(tag='video_list_table'):
		with dpg.theme_component(dpg.mvAll):
			dpg.add_theme_color(dpg.mvThemeCol_TableRowBgAlt, (47,47,48))
			

	# fonts
	with dpg.font_registry():
		dpg.add_font(file='font/Zain-Regular.ttf', tag='font_small', size=18)
		dpg.add_font(file='font/Zain-Regular.ttf', tag='font_medium', size=20)
		dpg.add_font(file='font/Zain-Regular.ttf', tag='font_global', size=24)
		dpg.add_font(file='font/Zain-Regular.ttf', tag='font_video_title', size=36)
		dpg.add_font(file='font/Zain-Regular.ttf', tag='font_video_formats', size=20)
	dpg.bind_font('font_global')


	# menu bar
	with dpg.viewport_menu_bar():
		with dpg.menu(tag='main_menu', label='Worker settings'):
			dpg.add_text('Num workers:')
			dpg.add_input_int(tag='worker_num', default_value=vimeo.worker_num, width=120, callback=set_worker_num)
			dpg.add_text('Worker timeout (minutes):')
			dpg.add_input_int(tag='worker_timeout', default_value=vimeo.worker_timeout, width=120, callback=set_worker_timeout)
		
	# main layout
	with dpg.window() as mainwin:		
		dpg.add_spacer(height=25)

		# top progress bar and status messages
		with dpg.group(horizontal=True):				
			dpg.add_button(label='Fetch video list', small=True, callback=get_user_video_list)
			dpg.add_progress_bar(tag='fetch_progress', height=20, default_value=-1, width=120)
			dpg.bind_item_theme(dpg.last_item(), 'app_progress_bar')
			dpg.add_loading_indicator(tag='loading', radius=1, color=(220,220,220), style=1, show=False)
			dpg.add_text('', tag='status')

		# main video list table 
		dpg.add_group(tag='video_list')

		# download button
		with dpg.group():
			dpg.add_spacer(height=10)
			with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
				dpg.add_table_column(init_width_or_weight=0.8)
				dpg.add_table_column(init_width_or_weight=0.2)
				with dpg.table_row():
					with dpg.table_cell():
						dpg.add_spacer(width=-1)
					with dpg.table_cell():
						dpg.add_button(tag='button_download_selected', label='Start Download', width=-1, show=False, callback=download_selected_videos)
						dpg.bind_item_theme(dpg.last_item(), 'download_button_theme')

	# start DPG
	dpg.setup_dearpygui()
	dpg.show_viewport()
	dpg.set_primary_window(mainwin, True)
	dpg.start_dearpygui()
	dpg.destroy_context()


# mp manager queue lock condition
if __name__ == '__main__':
    main_process()