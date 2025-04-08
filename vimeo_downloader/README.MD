# App usage:

**Important**: This app uses Playwright to fetch videos from your vimeo channel, you can configure the number of Workers (parallel browser instances) in the main menu. Be sure to use a responsible number of workers, with the risk of having slower response times or even a temporary block from vimeo, for hitting request rate limits!

1. Make sure to fill credentials.json file with your vimeo login.
2. Click "Fetch video list", it can take a while to fetch all data, depending on the number of videos you have on your channel.
3. Choose which video formats you wish to download (optionally use the search box to filter videos by name)
4. Click "Start download"
5. The video files will be saved to the "./downloads" folder
6. Next time you open the app, video list will load much faster, as the fetch results are cached to disk. If you wish to re-fetch the list, simply delete "cache.json" file from the app folder.
