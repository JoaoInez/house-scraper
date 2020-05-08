import urllib.request
import smtplib
import os
import schedule
import time
from email.message import EmailMessage
from bs4 import BeautifulSoup
from functools import reduce

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36'  # noqa: E501
}


def fetch_html(url):
    req = urllib.request.Request(
        url=url,
        headers=headers
    )
    res = urllib.request.urlopen(req)
    return res.read().decode('utf-8')


def send_email(apts):
    EMAIL_SENDER = os.getenv('EMAIL_SENDER')
    PASSWORD = os.getenv('PASSWORD')
    EMAIL_RECEIVERS = os.getenv('EMAIL_RECEIVERS').split(',')

    msg = EmailMessage()
    msg['Subject'] = 'Apartment(s) found!'
    msg['From'] = EMAIL_SENDER
    msg['To'] = ', '.join(EMAIL_RECEIVERS)

    def reducer(acc, apt):
        name = apt['name']
        link = apt['link']
        price = apt['price']
        return acc + f'{name}:\n{link}\n{price}€\n\n'

    message = reduce(reducer, apts, 'These apartments were found:\n\n')
    msg.set_content(message)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_SENDER, PASSWORD)

        smtp.send_message(msg)


def price_check(price):
    return 0 < price <= int(os.getenv('MAX_BUY_PRICE'))


def scrape_montepio():
    base_url = 'https://imoveismontepio.pt'

    def scrape_page(page=1, parsed_apartments=[]):
        html_doc = fetch_html(
            f'{base_url}{os.getenv("MONTEPIO_URL")}{page}'
        )
        soup = BeautifulSoup(html_doc, 'html.parser')

        apartments = soup.find_all('div', class_='property')

        if len(apartments):
            for apt in apartments:
                property_content = apt.find('div', class_='propertyContent')

                property_price = apt.find('p', class_='propertyPrice')

                for span in property_price.find_all('span'):
                    span.decompose()

                apt_price = property_price.get_text().strip()

                parsed_price = 0
                if '/' in apt_price:
                    parsed_price += int(''.join(apt_price.split('/')
                                                [0][:-2].split()))
                elif apt_price != 'Preço sob consulta':
                    parsed_price += int(''.join(apt_price[:-2].split()))

                if price_check(parsed_price):
                    apt_name = property_content.find(
                        'p', class_='propertyType').get_text().strip()

                    apt_link = base_url + property_content.a['href']

                    parsed_apt = {'name': apt_name,
                                  'link': apt_link, 'price': parsed_price}

                    parsed_apartments.append(parsed_apt)

            if len(apartments) == 8:
                return scrape_page(
                    page=page + 1, parsed_apartments=parsed_apartments
                )

        return parsed_apartments

    return scrape_page()


def scrape_houses():
    montepio_apts = scrape_montepio()

    if len(montepio_apts):
        send_email(montepio_apts)


schedule.every().day.at(os.getenv('SCHEDULED_TIME')).do(scrape_houses)

while True:
    schedule.run_pending()
    time.sleep(1)
