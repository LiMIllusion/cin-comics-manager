import sys
import argparse
import requests
from lxml import html
import datetime
import re
import json  # Import the json module for handling JSON files
import locale

# Imposta la localizzazione italiana
locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')

def extract_page_count(text):
    return int(text)
    
def sanitize_url(url):
    # Rimuovi 'http://', 'https://', 'www.', e tutto ciò che segue la barra '/'
    sanitized_url = re.sub(r'https?://|www\.|/.*$', '', url)
    return sanitized_url

def read_xpath_config(url):
    sanitized_url = sanitize_url(url)
    try:
        # Read the JSON file containing XPath configurations for a specific URL
        with open(f'xpath-{sanitized_url}.json', 'r') as config_file:
            xpath_config = json.load(config_file)
            return xpath_config
    except FileNotFoundError:
        print(f"XPath config file 'xpath-{sanitized_url}.json' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error parsing 'xpath-{sanitized_url}.json'. Make sure it's valid JSON.")
        sys.exit(1)

def read_config():
    try:
        # Read the JSON configuration file containing Notion API key and database ID
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)
            return config
    except FileNotFoundError:
        print("Config file 'config.json' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error parsing 'config.json'. Make sure it's valid JSON.")
        sys.exit(1)

def create_notion_page(url_to_scrape,xpath_config, config, status):
    # Extract Notion API key and database ID from the config
    notion_token = config.get("notion_token", "")
    notion_database_id = config.get("notion_database_id", "")
    print(notion_database_id)
    print(notion_token)
    
    if not notion_token or not notion_database_id:
        print("Invalid Notion API configuration.")
        sys.exit(1)

    # Perform web scraping of the page
    response = requests.get(url_to_scrape)
    tree = html.fromstring(response.content)

    # Extract information from the page using XPath expressions from xpath_config
    cover_image_url = tree.xpath(xpath_config["cover_image_xpath"])[0]
    pages_text = tree.xpath(xpath_config["pages_xpath"])[0].text
    page_count = extract_page_count(pages_text)

    if page_count is None:
        print("Unable to extract the page count.")
        return

    title = tree.xpath(xpath_config["title_xpath"])[0]
    content = tree.xpath(xpath_config["content_xpath"])[0]
    author = tree.xpath(xpath_config["author_xpath"])[0].text.strip()
    publication_text = tree.xpath(xpath_config["publication_date_xpath"])[0].text.strip()
    print(publication_text)
    publication_date = datetime.datetime.strptime(publication_text, '%d %b %Y').date()
    series = 'To Sort'
    # Map the -r, -b, -o, -w arguments to one of the desired "Status" values
    status_map = {"r": "To Read", "b": "To Buy", "o": "Ordered", "w": "Wishlist"}
    status_value = status_map.get(status, "To Read")

    # Create a data object to send to Notion API
    notion_data = {
        "parent": {"database_id": notion_database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Author": {"rich_text": [{"text": {"content": author}}]},
            "Publication": {"date": {"start": publication_date.isoformat()}},
            "Series": {"select": {"name": series}},
            "Status": {"select": {"name": status_value}},
            "Cover": {"files": [{"type": "external", "name": title, "external": {"url": cover_image_url}}]},
            "Pages": {"number": page_count}
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                "rich_text": [{ "type": "text", "text": { "content": content } }]
                }
            }
        ]     
    }
    print(notion_data)
    headers = {
        "Authorization": notion_token,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    # Send a POST request to the Notion API to create a new page
    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=notion_data)
    if response.status_code == 200:
        print("Page created successfully in Notion.")
    else:
        print(f"Error creating the page in Notion. Status code: {response.status_code}")


if __name__ == "__main__":
    print("AAAA")
    parser = argparse.ArgumentParser(description='Web scraping and Notion page creation')
    parser.add_argument('url', type=str, help='URL to scrape')
    parser.add_argument('-s', '--status', choices=['r', 'b', 'o', 'w'], default='r', help='Desired status (r, b, o, w)')
    args = parser.parse_args()

    url_to_scrape = args.url
    config = read_config()
    xpath_config = read_xpath_config(url_to_scrape)

    create_notion_page(url_to_scrape, xpath_config, config, args.status)
