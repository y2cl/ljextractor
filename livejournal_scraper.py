import requests
import logging
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import csv
import re
from datetime import datetime
import concurrent.futures
from typing import List, Dict, Optional
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('livejournal_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LiveJournalScraper:
    """
    A class used to scrape LiveJournal posts and comments.

    Attributes:
    ----------
    base_url : str
        The base URL of the LiveJournal blog.
    session : requests.Session
        A session object to persist parameters across requests.
    posts_data : List[Dict]
        A list of dictionaries containing post data.
    file_number : Dict[int, int]
        A dictionary to keep track of the file number for each year.
    csv_rows : List[Dict]
        A list of dictionaries containing CSV row data.
    comment_id : int
        A counter for the comment ID.
    timeout : int
        The timeout for requests in seconds.
    save_all_posts : bool
        A flag to indicate whether to save all posts or not.
    num_posts_to_save : int
        The number of posts to save.
    """

    def __init__(self, base_url: str, save_all_posts: bool, num_posts_to_save: int):
        """
        Initializes the LiveJournalScraper object.

        Parameters:
        ----------
        base_url : str
            The base URL of the LiveJournal blog.
        save_all_posts : bool
            A flag to indicate whether to save all posts or not.
        num_posts_to_save : int
            The number of posts to save.
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
        self.posts_data: List[Dict] = []
        self.file_number: Dict[int, int] = {}
        self.csv_rows: List[Dict] = []
        self.comment_id = 1
        self.timeout = 15
        self.save_all_posts = save_all_posts
        self.num_posts_to_save = num_posts_to_save

    def scrape_livejournal_page(self, url: str) -> None:
        """
        Scrapes a LiveJournal page.

        Parameters:
        ----------
        url : str
            The URL of the page to scrape.
        """
        try:
            # Send a GET request to the page
            response = self.session.get(url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            posts = soup.find_all('div', class_='asset-content')

            # Scrape each post
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {executor.submit(self.scrape_post, post): post for post in posts}
                for future in concurrent.futures.as_completed(futures):
                    post = futures[future]
                    try:
                        scraped_post = future.result()
                        if scraped_post:
                            self.posts_data.append(scraped_post)
                    except Exception as e:
                        logger.error(f"Error scraping {post}: {e}")

            # Save the data to an XML file if there are 50 posts or if we're saving all posts
            self.save_file()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve {url}: {e}")
            raise

    def scrape_post(self, post: BeautifulSoup) -> Optional[Dict]:
        """
        Scrapes a LiveJournal post.

        Parameters:
        ----------
        post : BeautifulSoup
            The post to scrape.

        Returns:
        -------
        Optional[Dict]
            A dictionary containing the post data or None if the post is not found.
        """
        try:
            # Find the post header
            post_header = post.find_previous('div', class_='asset-header-content-inner')
            if not post_header:
                logger.error("No post header found")
                return None

            # Extract the post title
            post_title_h2 = post_header.find('h2', class_='asset-name page-header2')
            post_title = post_title_h2.get_text(strip=True) if post_title_h2 else 'No Title'

            # Extract the post link
            post_link = post_header.find('a')['href'] if post_header.find('a') else 'No Link'

            # Extract the post date
            post_date = self.extract_date(post_link)

            # Extract the post content
            post_content = post.decode_contents()

            # Scrape the comments
            comments = self.scrape_comments(post_link)

            # Return the post data
            return {
                'Title': post_title,
                'Link': post_link,
                'Date': post_date,
                'Content': post_content,
                'Comments': comments
            }

        except Exception as e:
            logger.error(f"Error scraping post: {e}")
            return None

    def scrape_comments(self, post_url: str) -> List[Dict]:
        """
        Scrapes the comments of a LiveJournal post.

        Parameters:
        ----------
        post_url : str
            The URL of the post.

        Returns:
        -------
        List[Dict]
            A list of dictionaries containing the comment data.
        """
        try:
            # Send a GET request to the post
            response = self.session.get(post_url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            comment_sections = soup.find_all('div', class_='comment-inner')
            comments = []

            # Scrape each comment
            for comment_section in comment_sections:
                # Extract the comment author
                comment_author_div = comment_section.find('span', class_='ljuser')
                comment_author = comment_author_div.get_text(strip=True) if comment_author_div else 'Unknown Author'

                # Extract the comment author profile link
                comment_author_profile_link = comment_author_div.find('a', class_='i-ljuser-profile')['href'] if comment_author_div and comment_author_div.find('a', class_='i-ljuser-profile') else 'No Profile Link'

                # Extract the comment date
                comment_datetime_element = comment_section.find('abbr', class_='datetime comment-datetime')
                comment_date = comment_datetime_element['title'] if comment_datetime_element and 'title' in comment_datetime_element.attrs else comment_datetime_element.get_text(strip=True) if comment_datetime_element else 'NO DATE'
                comment_date = self.remove_utc(comment_date)
                comment_date = self.reformat_datetime(comment_date)

                # Extract the comment link
                comment_links_div = comment_section.find('div', class_='comment-links')
                comment_link = comment_links_div.find('a', class_='permalink')['href'] if comment_links_div and comment_links_div.find('a', class_='permalink') else 'No Link'

                # Extract the comment text
                comment_body_div = comment_section.find('div', class_='comment-body')
                comment_text = comment_body_div.decode_contents() if comment_body_div else 'No Comment'

                # Extract the comment ID
                comment_id = self.extract_ljcmt_id(comment_link)
                comment_id_value = comment_id[0] if comment_id else str(self.comment_id)

                # Extract the parent ID
                parent_link = comment_section.find('a', href=re.compile(r'thread=\d+'))
                if parent_link:
                    parent_url = parent_link['href']
                    thread_ids = self.extract_thread_ids(parent_url)
                    parent_id_value = thread_ids[0] if thread_ids else ''
                else:
                    parent_id_value = ''

                # Add the comment to the list
                comments.append({
                    'ID': comment_id_value,
                    'Post ID': str(self.file_number),
                    'Parent ID': parent_id_value,
                    'Author': comment_author,
                    'Author Profile Link': comment_author_profile_link,
                    'Date': comment_date,
                    'Link': comment_link,
                    'Text': comment_text
                })

                # Increment the comment ID
                self.comment_id += 1

            # Return the comments
            return comments

        except Exception as e:
            logger.error(f"Failed to scrape comments from {post_url}: {e}")
            return []

    def extract_ljcmt_id(self, url: str) -> List[str]:
        """
        Extracts the comment ID from a URL.

        Parameters:
        ----------
        url : str
            The URL to extract the comment ID from.

        Returns:
        -------
        List[str]
            A list of comment IDs.
        """
        try:
            # Send a GET request to the URL
            response = self.session.get(url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            ljcmt_ids = [div.get('id') for div in soup.find_all('div') if div.get('id') and div.get('id').startswith('ljcmt')]
            numerical_ids = [id.replace('ljcmt', '') for id in ljcmt_ids]

            # Return the comment IDs
            return numerical_ids

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while fetching the URL: {e}")
            return []
        except Exception as e:
            logger.error(f"An error occurred while parsing the HTML: {e}")
            return []

    def extract_thread_ids(self, url: str) -> List[str]:
        """
        Extracts the thread IDs from a URL.

        Parameters:
        ----------
        url : str
            The URL to extract the thread IDs from.

        Returns:
        -------
        List[str]
            A list of thread IDs.
        """
        try:
            # Send a GET request to the URL
            response = self.session.get(url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a')
            thread_ids = []

            # Extract the thread IDs
            for link in links:
                if link.text and 'Parent' in link.text:
                    href = link.get('href')
                    match = re.search(r'thread=([0-9]+)', href)

                    if match:
                        thread_id = match.group(1)
                        thread_ids.append(thread_id)

            # Return the thread IDs
            return thread_ids

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve {url}: {e}")
            return []
        except Exception as e:
            logger.error(f"An error occurred while parsing the HTML: {e}")
            return []

    def extract_date(self, url: str) -> str:
        """
        Extracts the date from a URL.

        Parameters:
        ----------
        url : str
            The URL to extract the date from.

        Returns:
        -------
        str
            The extracted date.
        """
        try:
            # Send a GET request to the URL
            response = self.session.get(url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            date_element = soup.find('abbr', class_='datetime')

            if date_element:
                date_str = date_element.text
                date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)

                date_formats = [
                    '%b. %d, %Y at %I:%M %p',
                    '%B %d, %Y at %I:%M %p',
                    '%d %B %Y at %I:%M %p',
                    '%m/%d/%Y %I:%M %p'
                ]

                for date_format in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, date_format)
                        date_obj = date_obj.replace(second=0, microsecond=0)
                        return date_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        continue

                return date_str
            else:
                logger.warning("No abbr element with class datetime found.")
                return ""

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return ""
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return ""

    def remove_utc(self, date_str: str) -> str:
        """
        Removes the UTC part from a date string.

        Parameters:
        ----------
        date_str : str
            The date string to remove the UTC part from.

        Returns:
        -------
        str
            The date string without the UTC part.
        """
        if '(UTC)' in date_str:
            return date_str.replace('(UTC)', '').strip()
        return date_str

    def reformat_datetime(self, date_str: str) -> str:
        """
        Reformats a date string to the desired format.

        Parameters:
        ----------
        date_str : str
            The date string to reformat.

        Returns:
        -------
        str
            The reformatted date string.
        """
        date_formats = [
            '%b. %d, %Y at %I:%M %p',
            '%B %d, %Y at %I:%M %p',
            '%d %B %Y at %I:%M %p',
            '%m/%d/%Y %I:%M %p'
        ]

        for date_format in date_formats:
            try:
                date_obj = datetime.strptime(date_str, date_format)
                date_obj = date_obj.replace(second=0, microsecond=0)
                return date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        return date_str

    def clean_date(self, date_str: str) -> str:
        """
        Cleans the date string by removing any suffix from the day part.

        Parameters:
        ----------
        date_str : str
            The date string to clean.

        Returns:
        -------
        str
            The cleaned date string.
        """
        date_part, time_part = date_str.split(', ')
        month, day_with_suffix = date_part.split(' ')
        day = re.sub(r'[^\d]', '', day_with_suffix)
        if len(day) == 1:
            day = '0' + day
        cleaned_date = f"{month} {day}, {time_part}"
        return cleaned_date

    def save_file(self) -> None:
        """
        Saves the scraped data to an XML file.
        """
        try:
            # Group posts by year
            posts_by_year = {}
            for post in self.posts_data:
                try:
                    year = datetime.strptime(post['Date'], '%Y-%m-%d %H:%M:%S').year
                except ValueError:
                    # If the post date is not in the expected format, write the title and URL to a separate CSV file
                    with open('invalid_post_dates.csv', 'a', newline='') as csvfile:
                        fieldnames = ['Title', 'URL']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        if csvfile.tell() == 0:
                            writer.writeheader()
                        writer.writerow({'Title': post['Title'], 'URL': post['Link']})
                    with open('log.txt', 'a') as log_file:
                        log_file.write(f"Failed to save post: {post['Title']} - {post['Link']}\n")
                    continue

                if year not in posts_by_year:
                    posts_by_year[year] = []
                posts_by_year[year].append(post)

            # Save each year to a separate file
            for year, posts in posts_by_year.items():
                if year not in self.file_number:
                    self.file_number[year] = 1

                # Split posts into chunks of 50
                chunks = [posts[i:i + 50] for i in range(0, len(posts), 50)]

                for chunk in chunks:
                    # Create the XML root element
                    root = ET.Element("rss")
                    root.set("version", "2.0")
                    root.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
                    root.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
                    root.set("xmlns:wp", "http://wordpress.org/export/1.2/")

                    # Create the channel element
                    channel = ET.SubElement(root, "channel")
                    title = ET.SubElement(channel, "title")
                    title.text = "LiveJournal Export"

                    description = ET.SubElement(channel, "description")
                    description.text = "Exported from LiveJournal"

                    wp_base_site_url = ET.SubElement(channel, "wp:base_site_url")
                    wp_base_site_url.text = self.base_url

                    wp_base_blog_url = ET.SubElement(channel, "wp:base_blog_url")
                    wp_base_blog_url.text = self.base_url

                    wp_wxr_version = ET.SubElement(channel, "wp:wxr_version")
                    wp_wxr_version.text = "1.2"

                    # Add each post to the XML file
                    for post in chunk:
                        item = ET.SubElement(channel, "item")
                        title = ET.SubElement(item, "title")
                        title.text = post['Title']

                        dc_creator = ET.SubElement(item, "dc:creator")
                        dc_creator.text = "AVGS"

                        content_encoded = ET.SubElement(item, "content:encoded")
                        content_encoded.text = post['Content'] + "\n\n<a href='" + post['Link'] + "'>Original Post</a>"

                        excerpt_encoded = ET.SubElement(item, "excerpt:encoded")
                        excerpt_encoded.text = ""

                        wp_post_id = ET.SubElement(item, "wp:post_id")
                        wp_post_id.text = str(self.file_number[year])

                        wp_post_date = ET.SubElement(item, "wp:post_date")
                        wp_post_date.text = post['Date']

                        wp_post_parent = ET.SubElement(item, "wp:post_parent")
                        wp_post_parent.text = "0"

                        wp_menu_order = ET.SubElement(item, "wp:menu_order")
                        wp_menu_order.text = "0"

                        wp_post_status = ET.SubElement(item, "wp:status")
                        wp_post_status.text = "publish"

                        wp_post_type = ET.SubElement(item, "wp:post_type")
                        wp_post_type.text = "post"

                        # Add each comment to the XML file
                        for comment in post['Comments']:
                            wp_comment = ET.SubElement(item, "wp:comment")
                            wp_comment_approved = ET.SubElement(wp_comment, "wp:comment_approved")
                            wp_comment_approved.text = "1"

                            wp_comment.set("type", "comment")

                            parent_id = comment['Parent ID'] if comment['Parent ID'] else "0"
                            wp_comment_parent = ET.SubElement(wp_comment, "wp:comment_parent")
                            wp_comment_parent.text = parent_id

                            wp_comment_id = ET.SubElement(wp_comment, "wp:comment_id")
                            wp_comment_id.text = comment['ID']

                            wp_comment_post_id = ET.SubElement(wp_comment, "wp:comment_post_id")
                            wp_comment_post_id.text = comment['Post ID']

                            wp_comment_author = ET.SubElement(wp_comment, "wp:comment_author")
                            wp_comment_author.text = comment['Author']

                            wp_comment_author_email = ET.SubElement(wp_comment, "wp:comment_author_email")
                            wp_comment_author_email.text = ""

                            wp_comment_author_url = ET.SubElement(wp_comment, "wp:comment_author_url")
                            wp_comment_author_url.text = comment['Author Profile Link']

                            # Clean the comment date
                            date_str = comment['Date']
                            cleaned_date = self.clean_date(date_str)
                            try:
                                date_obj = datetime.strptime(cleaned_date, '%b. %d, %Y %I:%M %p')
                            except ValueError:
                                # If the comment date is not in the expected format, write the title and URL to a separate CSV file
                                with open('invalid_comment_dates.csv', 'a', newline='') as csvfile:
                                    fieldnames = ['Title', 'URL']
                                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                    if csvfile.tell() == 0:
                                        writer.writeheader()
                                    writer.writerow({'Title': post['Title'], 'URL': post['Link']})
                                with open('log.txt', 'a') as log_file:
                                    log_file.write(f"Failed to save post: {post['Title']} - {post['Link']}\n")
                                continue

                            date_obj = date_obj.replace(second=0, microsecond=0)
                            wp_comment_date = ET.SubElement(wp_comment, "wp:comment_date")
                            wp_comment_date.text = date_obj.strftime('%Y-%m-%d %H:%M:%S')

                            wp_comment_content = ET.SubElement(wp_comment, "wp:comment_content")
                            wp_comment_content.text = comment['Text']

                    # Create the XML tree
                    tree = ET.ElementTree(root)

                    # Save the XML file
                    filename = f"livejournal_export_{year}_{self.file_number[year]}.xml"
                    try:
                        xml_string = ET.tostring(tree.getroot(), encoding='unicode')
                        with open(filename, 'w') as f:
                            f.write(xml_string)
                        logger.info(f"Saved {filename}")
                        with open('log.txt', 'a') as log_file:
                            for post in chunk:
                                log_file.write(f"Saved post: {post['Title']} - {post['Link']} to {filename}\n")
                    except Exception as e:
                        logger.error(f"Failed to save {filename}: {e}")
                        with open('log.txt', 'a') as log_file:
                            for post in chunk:
                                log_file.write(f"Failed to save post: {post['Title']} - {post['Link']}\n")

                    # Add each post to the CSV rows
                    for post in chunk:
                        self.csv_rows.append({
                            'Title': post['Title'],
                            'Date': post['Date'],
                            'XML File': filename
                        })

                    # Increment the file number for the year
                    self.file_number[year] += 1

            # Reset the posts data
            self.posts_data = []

        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise

    def get_all_pages(self) -> None:
        """
        Gets all pages of the LiveJournal blog.
        """
        url = self.base_url
        while True:
            try:
                # Send a GET request to the page
                response = self.session.get(url, timeout=self.timeout, verify=True)
                response.raise_for_status()

                # Parse the HTML content
                soup = BeautifulSoup(response.content, 'html.parser')
                posts = soup.find_all('div', class_='asset-content')

                # If there are no posts, break the loop
                if not posts:
                    break

                # Scrape the page
                self.scrape_livejournal_page(url)

                # Find the previous link
                prev_link = soup.find('a', class_='prev')
                if prev_link:
                    url = prev_link['href']
                else:
                    break

            except Exception as e:
                logger.error(f"Failed to get all pages: {e}")
                break

    def get_one_post(self, post_url: str) -> None:
        """
        Gets one post from the LiveJournal blog.

        Parameters:
        ----------
        post_url : str
            The URL of the post.
        """
        try:
            # Send a GET request to the post
            response = self.session.get(post_url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            post = soup.find('div', class_='asset-content')

            # If the post is not found, log an error and return
            if not post:
                logger.error("No post found")
                return

            # Find the post header
            post_header = post.find_previous('div', class_='asset-header-content-inner')
            if not post_header:
                logger.error("No post header found")
                return

            # Extract the post title
            post_title_h2 = post_header.find('h2', class_='asset-name page-header2')
            post_title = post_title_h2.get_text(strip=True) if post_title_h2 else 'No Title'

            # Extract the post link
            post_link = post_header.find('a')['href'] if post_header.find('a') else 'No Link'

            # Extract the post date
            post_date = self.extract_date(post_link)

            # Extract the post content
            post_content = post.decode_contents()

            # Scrape the comments
            comments = self.scrape_comments(post_link)

            # Add the post to the posts data
            self.posts_data.append({
                'Title': post_title,
                'Link': post_link,
                'Date': post_date,
                'Content': post_content,
                'Comments': comments
            })

            # Save the file
            self.save_file()

        except Exception as e:
            logger.error(f"Failed to get one post: {e}")
            raise

def main():
    """
    The main function.
    """
    # Validate user input
    while True:
        base_url = input("Enter the base URL of the LiveJournal blog: ")
        if base_url:
            break
        else:
            print("Invalid input. Please enter a valid URL.")

    # Ask the user how many posts to save
    while True:
        print("Select an option:")
        print("1. Save all posts")
        print("2. Save a specific number of posts")
        print("3. Save one post")
        print("4. Change LiveJournal Blog URL")
        print("5. Exit")

        option = input("Enter your choice (1/2/3/4/5): ")

        if option == "1":
            save_all_posts = True
            num_posts_to_save = 0
            break
        elif option == "2":
            save_all_posts = False
            while True:
                try:
                    num_posts_to_save = int(input("Enter the number of posts to save: "))
                    if num_posts_to_save > 0:
                        break
                    else:
                        print("Invalid input. Please enter a positive integer.")
                except ValueError:
                    print("Invalid input. Please enter a positive integer.")
            break
        elif option == "3":
            save_all_posts = False
            num_posts_to_save = 1
            break
        elif option == "4":
            base_url = input("Enter the new base URL of the LiveJournal blog: ")
            if base_url:
                continue
            else:
                print("Invalid input. Please enter a valid URL.")
        elif option == "5":
            return
        else:
            print("Invalid option. Please try again.")

    # Create a LiveJournalScraper object
    scraper = LiveJournalScraper(base_url, save_all_posts, num_posts_to_save)

    # Get all pages or one post
    if num_posts_to_save == 1:
        post_url = input("Enter the URL of the post: ")
        scraper.get_one_post(post_url)
    else:
        scraper.get_all_pages()

    # Save the CSV file
    if scraper.posts_data:
        scraper.save_file()

    csv_filename = f"livejournal_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = ['Title', 'Date', 'XML File']
        writer = csv.DictWriter(csvfile, fieldnames)
        writer.writeheader()
        for row in scraper.csv_rows:
            writer.writerow(row)
    logger.info(f"Saved {csv_filename}")

    # Ask the user if they want to continue
    while True:
        cont = input("Do you want to continue? (y/n): ")
        if cont.lower() == "y":
            break
        elif cont.lower() == "n":
            return
        else:
            print("Invalid input. Please enter y or n.")

if __name__ == "__main__":
    main()

# Created by J Horsley III
# https://y2cl.net
# https://github.com/y2cl/ljextractor
