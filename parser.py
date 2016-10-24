#!/usr/bin/python3

# Author:    Evert Heylen
# License:   WTFPL
# Depencies: selenium (and python bindings), python-icalendar and firefox.

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0
from selenium.webdriver.support import expected_conditions as EC # available since 2.26.0

from icalendar import Calendar, Event

from getpass import getpass
from datetime import *
from time import sleep
import re


# ----[ Settings ]------------------------------------------

user = input("User: ")
password = getpass()

filename = input("Filename (without extension)? ") + ".ics"

room_row = 5  # M.G.010
building = "CMI - gebouw G"

# ATTENTION: only specify the first day of a month here
start = date(2016,9,1)
end = date(2017,1,1)

# ----------------------------------------------------------


_ua_5000 = date(2013,9,9)  # do not change
start_num = (start - _ua_5000).days + 5000
end_num = (end - _ua_5000).days + 5000

#print(start_num)
#print(end_num)

def main():
    # initialize the calendar
    cal = Calendar()
    cal.add("summary", "Generated by lokaal-parser, made by Evert Heylen.")
    cal.add('prodid', '-//lokaal parser//evertheylen.appspot.com//')
    cal.add('version', '2.0')
    
    # login prompt
    br = webdriver.Chrome()
    br.implicitly_wait(2)  # ...
    br.get("https://www.ua.ac.be/login/login.aspx?url=www.ua.ac.be&c=.LOKAALRESERVATIE&n=36899")
    br.find_element_by_id("TextBox1").send_keys(user)
    br.find_element_by_id("TextBox2").send_keys(password)
    br.find_element_by_name("Button1").click()

    # open 'lokalengebruik'
    br.get("http://www.ua.ac.be/main.aspx?c=.LOKAALRESERVATIE&n=43599&ct=43846")
    select = Select(br.find_element_by_name("ctl18$ddlGebouwen"))
    select.select_by_visible_text(building)
    
    # navigate to first month
    current_first = first_day(br)
    while current_first != start:
        print("current_first", current_first, "start", start)
        if current_first < start:
            next_month(br)
        else:
            prev_month(br)
        sleep(1)
        current_first = first_day(br)
    
    print("Currently at the right month.")
    
    current_day = start
    days = get_days(br)
    days[current_day].click()
    days = get_days(br)
    
    while current_day != end:
        # have to redo this every loop, because of the DOM being reconstructed etc...
        days = get_days(br)
        
        # ------- do something with current_day, actual parsing is here ---------
        print('parse',current_day)
        
        """
        //*[@id="ctl18_lblBeforeBody"]/table/tbody/tr[2]/td/table/tbody/tr[1]/td/p[3]/table/tbody/tr[5]/td[2]/img
        ...
        //*[@id="ctl18_lblBeforeBody"]/table/tbody/tr[2]/td/table/tbody/tr[1]/td/p[3]/table/tbody/tr[5]/td[61]/img
        """
        
        # current also contains the time
        current = datetime(current_day.year, current_day.month, current_day.day, 7, 0, 0)
        event = None
        #event = Event()  # ignore the first event
        #event.add('dtstart', start)
        #event.add('summary', 'Ignore me!')
        
        for i in range(2,62):
            cell = br.find_element_by_xpath('//*[@id="ctl18_lblBeforeBody"]/table/tbody/tr[2]/td/table/tbody/tr[1]/td/p[3]/table/tbody/tr[5]/td[{0}]/img'.format(i))
            
            taken = cell.get_attribute("src") == "http://www.ua.ac.be/plugins/ua/context/cde/images/bezet.gif"
            summ = ''
            close = False
            new = False
            if taken:
                summ = parse_summ(cell.get_attribute("onclick"))
            
                if (not event is None) and str(event["SUMMARY"]) != summ:
                    # close old event, make new event
                    close = True
                    new = True
                elif event is None:
                    # make new event
                    new = True
            elif not event is None:
                # close old event
                close = True
            
            # do the actions chosen
            if close:
                # end time
                event.add('dtend', current-timedelta(minutes=15))  # possible bug. I don't care.
                cal.add_component(event)
                #print("added {}, from {} to {}".format(str(event['SUMMARY']), str(event['DTSTART']), str(event['DTEND'])))
                event = None
            
            if new:
                event = Event()
                # start time
                event.add('dtstart', current)
                event.add('summary', summ)
            
            # next current
            current += timedelta(minutes=15)
        # -------
        
        current_day += timedelta(days=1)
        if current_day in days:
            days[current_day].click()  # next day
        else:
            # go to next month
            next_month(br)
            sleep(1)
            days = get_days(br)
            days[current_day].click()
    
        
    br.close()
    
    # save calendar
    f = open(filename, 'wb')
    f.write(cal.to_ical())
    f.close()
    print("Written file to %s"%filename)
    
    print("All done!")
    
    

def num_to_date(num):
    return _ua_5000 + timedelta(days=(num-5000))


def next_month(br):
    br.find_element_by_xpath('//*[@id="ctl18_Calendar1"]/tbody/tr[1]/td/table/tbody/tr/td[3]/a').click()

def prev_month(br):
    br.find_element_by_xpath('//*[@id="ctl18_Calendar1"]/tbody/tr[1]/td/table/tbody/tr/td[1]/a').click()


def first_day(br):
    for row in range(3,9):
        for col in range(1,8):
            el = br.find_element_by_xpath('//*[@id="ctl18_Calendar1"]/tbody/tr[{0}]/td[{1}]/a'.format(row, col))
            if "darkgray" not in el.get_attribute("style"):
                return num_to_date(parse_num(el.get_attribute("href")))

    
def get_days(br):
    days = {}
    
    for row in range(3,9):
        for col in range(1,8):
            el = br.find_element_by_xpath('//*[@id="ctl18_Calendar1"]/tbody/tr[{0}]/td[{1}]/a'.format(row, col))
            if "darkgray" not in el.get_attribute("style"):
                num = parse_num(el.get_attribute("href"))
                date = num_to_date(num)
                days[date] = el
    
    return days
    
    """
    //*[@id="ctl18_Calendar1"]/tbody/tr[3]/td[1]/a
      ...
    //*[@id="ctl18_Calendar1"]/tbody/tr[3]/td[7]/a
    .....
    .....
    //*[@id="ctl18_Calendar1"]/tbody/tr[8]/td[1]/a
      ...
    //*[@id="ctl18_Calendar1"]/tbody/tr[8]/td[7]/a
    """

_parse_num = re.compile(r"javascript:__doPostBack\('ctl18\$Calendar1','([0-9]*)'\)")
def parse_num(s):
    return int(_parse_num.sub(r"\1", s))

def parse_summ(s):
    return s[7:-3].replace("\\n", "\n")

def diff_months(a, b):
    return (b.year - a.year)*12 + (b.month - a.month)




if __name__ == '__main__':
    main()
