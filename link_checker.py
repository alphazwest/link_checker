# Standard imports
import time
import requests
from typing import List
import bs4
import json
import tldextract
import logging

# set the logging level here -- goes to stdout
logging.getLogger().setLevel(logging.INFO)


def make_request(url: str) -> requests.Response:
    """
    Makes a http GET request for a URL and returns a requests Response object
    Note: You can implement a proxy request here if you need.
    Args:
        url: str - a URL for which an HTTP GET request is made
    Returns:
        requests Response object
    """
    return requests.get(url=url)


def get_medium_article_links(url: str) -> List[str]:
    """
    Gets a list of URL strings from a Medium.com author profile to the
    articles having been published previously
    """
    logging.info(f'Getting links from medium url: {url}')

    # makes the http request using the custom wrapper function
    data = make_request(url)

    # parse the response data using BS4
    soup = bs4.BeautifulSoup(data.text, 'lxml')

    # For each article link available, extracts the link to that
    # article and reconstructs the absolute URL version, taking
    # into account any initial redirects that may have resulted
    # in links being relative to a branded subdomain vs. medium.com
    # e.g. publisher.medium.com/url vs. medium.com/@publisher/url
    articles = soup.find_all('article')
    links = []
    for article in articles:

        # Gets the first list, reconstructs url, collects to output
        link = article.find('a')
        if link:
            href = f"{data.url[:-1] if data.url[-1] == '/' else data.url}{link['href']}"
            href = href.split('?')[0] if "?" in href else href  # remove tracking params
            links.append(href)

    return links


def extract_href(a: bs4.Tag, current_domain: str, scheme: str = "https", strip_params: bool = True) -> str:
    """
    Extracts the anchor text from a link accounting for relativized links
    """
    logging.info(f'Extracting href from link: {str(a)}')

    # return empty string if anchor not available
    try:
        href = a['href']
    except AttributeError:
        return ''

    # Strip params if desired
    if strip_params:

        # Keep params for some know ok website (e.g. youtube)
        if not any(x in href for x in ['youtube.com/watch']):
            href = href.split('?')[0]

    # reconstitute relativized links
    if href[0] == '/':
        href = f"{scheme}://{current_domain}{href}"

    return href


def check_medium_article_links(url: str) -> List['Link']:
    """
    Given a URL link to a medium.com format article, checks each
    link for validity, anchor text, http status, and saves a redirect chain if found.
    """
    logging.info(f'Checking links from Medium URL: {url}')
    data = make_request(url)
    soup = bs4.BeautifulSoup(data.text, 'lxml')
    article = soup.find('article')

    # Get the current domain to relativize links
    current_domain = tldextract.extract(url).fqdn

    # extract all links
    links = []
    for a in article.find_all('a'):

        # Save a new Link object
        the_link = Link.create_link(
            url=extract_href(
                a=a,
                current_domain=current_domain)
            ,
            anchor=a.get_text(strip=True))

        if the_link:
            links.append(
                the_link
            )

    return links


class Link:
    def __init__(self, url: str, anchor: str, http_status: int, redirect_chain: List[str] = None):

        self.url = url
        self.anchor = anchor
        self.http_status = http_status

        # use given or create empty list
        self.redirect_chain = redirect_chain if redirect_chain else []

        # final URL is last in redirect chain or given URL if no redirect chain found
        self.final_url = self.url if len(self.redirect_chain) == 0 else self.redirect_chain[-1]

    @staticmethod
    def create_link(url: str, anchor: str) -> 'Link' or None:
        """Create a link from just a URL and anchor"""
        data = make_request(url=url)
        if not data:
            return None

        redirects = []
        for r in data.history:
            redirects.append(r.url)

        return Link(url=url, anchor=anchor, http_status=data.status_code, redirect_chain=redirects)

    def to_dict(self):
        """
        Creates a serializable format of a Link object
        """
        return {
            "url": self.url,
            "anchor": self.anchor,
            "http_status": self.http_status,
            "redirect_chain": self.redirect_chain,
            "final_url": self.final_url
        }
    
    
def check_medium_links(profile_url: str) -> List[dict]:
    """
    Given a link to a Medium author's story feed, obtains all recent article links 
    and checks the links from each article for http status (e.g. 200 vs. 404) and
    returns a list of dictionary objects as such:
    [
        {
            'url': link,
            'timestamp': unix_format_timestamp
            'links': [list of Link.to_dict() objects]
        },
        ]
        
    Notes:
        Will accommodate either a publisher.medium.com or medium.com/@publisher format
        link to an author's profile.

    """
    links = get_medium_article_links(profile_url)

    output = []
    for link in links:
        article_links = check_medium_article_links(url=link)

        output.append(
            {
                'url': link,
                'timestamp': str(time.time()),
                'links': [l.to_dict() for l in article_links]
            }
        )
    return output
    