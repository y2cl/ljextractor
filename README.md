# LiveJournal Scraper
A Python script to scrape posts and comments from a LiveJournal blog.

## Table of Contents
* [Introduction](#introduction)
* [Requirements](#requirements)
* [Installation](#installation)
* [Usage](#usage)
* [Options](#options)
* [Output](#output)
* [Troubleshooting](#troubleshooting)
* [Contributing](#contributing)
* [License](#license)

## Introduction
This script is designed to scrape posts and comments from a LiveJournal blog. It uses the `requests` and `BeautifulSoup` libraries to send HTTP requests to the blog and parse the HTML responses.

## Requirements
* `python` (version 3.6 or later)
* `requests` (install with `pip install requests`)
* `beautifulsoup4` (install with `pip install beautifulsoup4`)
* `xml.etree.ElementTree` (included with Python)
* `csv` (included with Python)
* `re` (included with Python)
* `datetime` (included with Python)
* `concurrent.futures` (included with Python)
* `logging` (included with Python)

  See the [REQUIREMENTS.TXT](REQUIREMENTS) file for more information.

## Installation
1. Clone this repository to your local machine using `git clone https://github.com/your-username/livejournal-scraper.git`
2. Install the required libraries using `pip install -r requirements.txt`

## Usage
1. Run the script using `python livejournal_scraper.py`
2. Follow the prompts to enter the base URL of the LiveJournal blog and select the options you want to use.

## Options
* **Save all posts**: Save all posts from the blog to XML files.
* **Save a specific number of posts**: Save a specific number of posts from the blog to XML files.
* **Save one post**: Get a single post from the blog and save it to an XML file.
* **Change LiveJournal Blog URL: Set a new base URL.
* **Exit: Exit script

## Output
The script will output the following files:
* `livejournal_export_YYYYMMDDHHMMSS.csv`: A CSV file containing the titles, dates, and XML file names of the saved posts.
* `livejournal_export_YYYY_1.xml`, `livejournal_export_YYYY_2.xml`, etc.: XML files containing the posts and comments from the blog.
* `log.txt`: A log file containing information about the posts that were saved and any errors that occurred.

## Troubleshooting
* If you encounter any errors while running the script, check the `log.txt` file for more information.
* If you are having trouble with the script, try updating the `requests` and `beautifulsoup4` libraries to the latest versions.

## Contributing
If you would like to contribute to this project, please fork the repository and submit a pull request with your changes.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

________________________________________________________________________________________________________________

##### Created by J Horsley III
[http://y2cl.net](y2cl.net)
