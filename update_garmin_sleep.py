"""
Pull my Garmin sleep data via json requests.

This script was adapted from: https://github.com/kristjanr/my-quantified-sleep
The aforementioned code required the user to manually define
headers and cookies.  It also stored all of the data within Night objects.

My modifications include using selenium to drive a Chrome browser.  This avoids
the hassle of getting headers and cookies manually (the cookies would have to be updated
everytime the Garmin session expired).  It also segments data requests because
Garmin will respond with an error if more than 32 days are requested at once.  Lastly,
data is stored as a pandas dataframe and then written to a user-defined directory
as a pickle file.

Data is this processed and merged with older data from my Microsft smartwatch.
The merged data is also saved as pandas dataframes in pickle files.

Lastly, sunrise and sunset data is downloaded for all days in the sleep dataset.
This data is also archived as a pandas dataframe and saved as a pickle file.

The data update process hs been broken into steps so that progress can be passed
to the Dash app.
"""
# import base packages
import datetime, json, os, re, sys
from itertools import chain
from os.path import isfile

# import installed packages
import pytz, requests, chardet, brotli
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar as calendar
from seleniumwire import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

# input variables
if os.name == "nt":
    # running on my local Windows machine
    ENV = "local"
else:
    # running on heroku server
    ENV = "heroku"

if ENV == "local":
    proj_path = "C:/Users/adiad/Anaconda3/envs/SleepApp/sleep_app/"  # read/write data dir
else:
    proj_path = ""
    GOOGLE_CHROME_PATH = '/app/.apt/usr/bin/google-chrome'
    CHROMEDRIVER_PATH = '/app/.chromedriver/bin/chromedriver'

garmin_results_pkl_fn = "data/garmin_sleep_df.pkl"  # name of pickle file to archive (combining new results with any previous Garmin) for easy updating and subsequent processing
garmin_results_json_fn = "data/new_garmin_sleep.json"  # name of json file with only new raw results
garmin_results_csv_fn = "data/garmin_sleep_df.csv"  # name of csv file to archive (combining new results with any previous)
all_descr_results_fn = "data/all_sleep_descr_df.pkl" # name of pickle file combining all Garmin & Microsift sleep session description data
all_event_results_fn = "data/all_sleep_event_df.pkl" # name of pickle file combining all Garmin & Microsoft event data
sun_pkl_fn = "data/sun_df.pkl" # name of pickel file to archive sunrise/sunset data
local_tz = "US/Eastern" # pytz local timezone for sunrise/sunset time conversion
sun_lat = 39.76838 # latitude where sunrise/sunset times are derived from
sun_lon = -86.15804 # longitude where sunrise/sunset times are derived from
run_browser_headless = False  # will hide Firefox during execution if True
browser_action_timeout = 60  # max time (seconds) for browser wait operations
start_date = '2017-03-01'  # first date to pull sleep data
end_date = str(datetime.date.today() - datetime.timedelta(days=1))  # last date to pull sleep data
user_name = "email address"  # Garmin username
password = "password"  # Garmin password
signin_url = "https://connect.garmin.com/signin/"  # Garmin sign-in webpage
sleep_url_base = "https://connect.garmin.com/modern/sleep/"  # Garmin sleep base URL (sans date)
sleep_url_json_req = "https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySleepsByDate"


def download(start_date, end_date, headers, session_id):
    params = (
        ('startDate', start_date),
        ('endDate', end_date),
        ('_', session_id),
    )

    response = requests.get(sleep_url_json_req, headers=headers, params=params)
    if response.status_code != 200:
        print("RESPONSE ERROR RECEIVED:")
        print('Status code: %d' % response.status_code)
        response_dict = json.loads(response.content.decode('UTF-8'))
        print('Content: %s' % response_dict["message"])
        raise Exception
    return response


def download_to_json(start_date, end_date, headers, session_id):
    response = download(start_date, end_date, headers, session_id)

    # most responses are in ascii (no encoding)
    # sporadically a response will have brotli encoding

    #print("The response is encoded with:", chardet.detect(response.content))
    if chardet.detect(response.content)["encoding"] == 'ascii':
        return json.loads(response.content)
    else:
        return brotli.decompress(response.content)
    

def converter(data, return_df=True):
    # define functions which pass through None value because
    # datetime functions don't accept value None
    def sleep_timestamp(val):
        if val is None:
            return None
        else:
            return datetime.datetime.fromtimestamp(val / 1000, pytz.utc)
    

    def sleep_timedelta(val):
        if val is None:
            return None
        else:
            return datetime.timedelta(seconds=val)


    # initialize variables
    if return_df:
        nights = pd.DataFrame(columns=["Prev_Day", "Bed_Time", "Wake_Time",
                                       "Awake_Dur", "Light_Dur", "Deep_Dur", 
                                       "Total_Dur", "Nap_Dur", "Window_Conf"])
        i = 0
    else:
        nights = []
    
    for d in data:
        bed_time = sleep_timestamp(d['sleepStartTimestampGMT'])
        wake_time = sleep_timestamp(d['sleepEndTimestampGMT'])
        previous_day = datetime.date(*[int(datepart) for datepart in d['calendarDate'].split('-')]) - datetime.timedelta(days=1)
        deep_duration = sleep_timedelta(d['deepSleepSeconds'])
        light_duration = sleep_timedelta(d['lightSleepSeconds'])
        total_duration = sleep_timedelta(d['sleepTimeSeconds'])
        awake_duration = sleep_timedelta(d['awakeSleepSeconds'])
        nap_duration = sleep_timedelta(d['napTimeSeconds'])
        window_confirmed = d['sleepWindowConfirmed']

        if return_df:
            nights.loc[i] = [previous_day, bed_time, wake_time, awake_duration, 
                             light_duration, deep_duration, total_duration, 
                             nap_duration, window_confirmed]
            i += 1
        else:
            night = Night(bed_time, wake_time, previous_day, deep_duration, 
                          light_duration, total_duration, awake_duration)
            nights.append(night, sort=True)
    
    return nights


# this function returns a list of all dates in [date1, date2]
def daterange(date1, date2):
    date_ls = [date1]
    for n in range(int((date2 - date1).days)):
        date_ls.append(date_ls[-1] + datetime.timedelta(days=1))
    return date_ls


# steps to updating sleep data:
# Step 0: determine which dates are missing in the archived Garmin dataset,
#         given the input start & end dates
# Step 1: Login to connect.garmin.com, get user setting credentials
# Step 2: Using credentials, download missing data from Garmin in json
# Step 3: process new Garmin data, merge it with archived data
# Step 4: download sunrise/sunset data for new dates and merge with archived data
def step0():
    # make a list of all dates from first sleep date to last (fills any missing dates)
    req_dates_ls = daterange(
        datetime.datetime.strptime(start_date, "%Y-%m-%d").date(), 
        datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    )

    # Look for previous results
    if isfile(proj_path + garmin_results_pkl_fn):
        nights_df = pd.read_pickle(proj_path + garmin_results_pkl_fn)
    else:
        nights_df = pd.DataFrame()

    # if previous results were found, reduce requested dates to those not yet obtained
    if len(nights_df) > 0:

        # get list of requested dates not yet obtained 
        archive_dates_ls = list(nights_df["Prev_Day"])
        new_req_dates_ls = np.setdiff1d(req_dates_ls, archive_dates_ls)
    else:
        new_req_dates_ls = req_dates_ls
    
    #print("Archive max: ", max(archive_dates_ls))
    #print("Request max: ", max(req_dates_ls))
    if len(new_req_dates_ls) == 0:
        msg = "Archived data is up to date, no new data is available"

    else:
        msg = "Current data was checked and " + str(len(new_req_dates_ls)) + " night(s) are needed"
    return [msg, nights_df, new_req_dates_ls]


def step1():
    opts = webdriver.ChromeOptions()
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    if ENV == "local":
        if run_browser_headless:
            opts.addArgument("headless")
            assert opts.headless  # Operating in headless mode
    else:
        opts.binary_location = GOOGLE_CHROME_PATH

    # open firefox and goto Garmin's sign-in page
    print("Opening Chrome browser")
    driver = webdriver.Chrome(chrome_options=opts)
    driver.get(signin_url)

    # wait until sign-in fields are visible
    wait = WebDriverWait(driver, browser_action_timeout)
    wait.until(ec.frame_to_be_available_and_switch_to_it(("id","gauth-widget-frame-gauth-widget")))
    wait.until(ec.presence_of_element_located(("id","username")))

    # write login info to fields, then submit
    print("Signing in to connect.garmin.com")
    element = driver.find_element_by_id("username")
    driver.implicitly_wait(5)
    element.send_keys(user_name)
    element = driver.find_element_by_id("password")
    element.send_keys(password)
    element.send_keys(Keys.RETURN)

    wait.until(ec.url_changes(signin_url))  # wait until landing page is requested
    driver.switch_to.default_content()  # get out of iframe

    # get dummy webpage to obtain all request headers
    print("Loading dummy page to obtain headers")
    driver.get(sleep_url_base + start_date)
    request = driver.wait_for_request(sleep_url_base + start_date, 
                                      timeout=browser_action_timeout)
    if (request.response.status_code != 200) | (~ hasattr(request, "headers")):
        print("RESPONSE ERROR RECEIVED:")
        if (request.response.status_code != 200):
            print("Status code: %d" % request.response.status_code)
            #response_dict = json.loads(request.content.decode('UTF-8'))
            print("Reason: ", request.response.reason)
        if (~ hasattr(request, "headers")):
            print("Request did not have 'headers' attribute")
            print("Request attributes: ", dir(request))
            print("Request headers: ", request.headers)
        #raise Exception

    # close the Firefox browser
    driver.close()

    msg = "Logged in to connect.garmin.com"
    return [msg, request]


def step2(request, new_req_dates_ls):
    # transfer request headers
    headers = {
        "cookie": request.headers["Cookie"],
        "referer": sleep_url_base + start_date,
        "accept-encoding": request.headers["Accept-Encoding"],
        "accept-language": "en-US", # request.headers["Accept-Language"],
        "user-agent": request.headers["User-Agent"],
        #"nk": "NT",
        "accept": request.headers["Accept"],
        "authority": request.headers["Host"],
        #"x-app-ver": "4.25.3.0",
        "upgrade-insecure-requests": request.headers["Upgrade-Insecure-Requests"]
    }

    # get the session id from the headers
    re_session_id = re.compile("(?<=\$ses_id:)(\d+)")
    session_id = re_session_id.search(str(request.headers)).group(0)

    # Garmin will throw error if request time span exceeds 32 days
    # therefore, request 32 days at a time
    max_period_delta = datetime.timedelta(days=31)
    data = []  # list of jsons, one per time period
    get_dates_ls = new_req_dates_ls
    while len(get_dates_ls) > 0:
        period_start = min(get_dates_ls)
        if (max(get_dates_ls) - period_start) > (max_period_delta - datetime.timedelta(days=1)):
            period_end = period_start + max_period_delta
        else:
            period_end = max(get_dates_ls)

        # note, this may request some dates which were already obtained
        # since a contiguous period is being requested rather than 32 new dates
        # duplicated dates will be dropped later
        print("Getting data for period: [%s, %s]" % (period_start, period_end))
        data.append(download_to_json(period_start, period_end, headers, session_id))

        # trim dates list
        get_dates_ls = [d for d, s in zip(get_dates_ls, np.array(get_dates_ls) > period_end) if s]

    # combine list of jsons into one large json
    data = list(chain.from_iterable(data))

    # save raw Garmin json to project folder
    with open(proj_path + garmin_results_json_fn, 'w') as fp:
        json.dump(data, fp)
    
    msg = "Data has been downloaded from Garmin"
    return [msg, data]


def step3(nights_df, data, new_req_dates_ls):
    # clean the new garmin data
    new_nights_df = converter(data)
    new_nights_df["Prev_Day"] = pd.to_datetime(new_nights_df["Prev_Day"])
    if pd.to_datetime(new_nights_df["Bed_Time"]).dt.tz is None:
        new_nights_df["Bed_Time"] = pd.to_datetime(new_nights_df["Bed_Time"]). \
            dt.tz_localize(local_tz)
    else:
        new_nights_df["Bed_Time"] = pd.to_datetime(new_nights_df["Bed_Time"]). \
            dt.tz_convert(local_tz)
    if pd.to_datetime(new_nights_df["Wake_Time"]).dt.tz is None:
        new_nights_df["Wake_Time"] = pd.to_datetime(new_nights_df["Wake_Time"]). \
            dt.tz_localize(local_tz)
    else:
        new_nights_df["Wake_Time"] = pd.to_datetime(new_nights_df["Wake_Time"]). \
            dt.tz_convert(local_tz)
    new_nights_df["Light_Dur"] = pd.to_timedelta(new_nights_df["Light_Dur"], "days")
    new_nights_df["Deep_Dur"] = pd.to_timedelta(new_nights_df["Deep_Dur"], "days")
    new_nights_df["Total_Dur"] = pd.to_timedelta(new_nights_df["Total_Dur"], "days")
    new_nights_df["Nap_Dur"] = pd.to_timedelta(new_nights_df["Nap_Dur"], "days")

    # fill df with missing dates so that subsequent updates won't keep
    # requesting data which Garmin doesn't have
    new_missing_dates_ls = np.setdiff1d(new_req_dates_ls, new_nights_df["Prev_Day"].dt.date)
    new_missing_row = [pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT, np.NAN]
    for d in new_missing_dates_ls:
        new_nights_df.loc[len(new_nights_df)] = [d] + new_missing_row

    # drop any nights which were already in the archived pickle file,
    # then merge it with archived data
    if len(nights_df) > 0:
        new_nights_df = new_nights_df[~new_nights_df["Prev_Day"].isin(nights_df["Prev_Day"])]
        nights_df = nights_df.append(new_nights_df, sort=True).sort_values("Prev_Day", axis=0)
    else:
        nights_df = new_nights_df.sort_values("Prev_Day", axis=0)
    
    # trim most recent nights which have NaT durations because they were likely caused
    # by the smartwatch not yet having synced with Garmin for those dates
    unknown_nights_ls = []
    i = 1
    while pd.isnull(nights_df.Total_Dur.iloc[-i]) & (len(nights_df) >= i):
        unknown_nights_ls.append(nights_df.Prev_Day.iloc[-i])
        i += 1
    nights_df = nights_df[~nights_df["Prev_Day"].isin(unknown_nights_ls)]

    # save merged results
    #nights_df.to_csv(proj_path + garmin_results_csv_fn)
    nights_df.to_pickle(proj_path + garmin_results_pkl_fn)

    # clean garmin data for dashboard
    garmin_df = nights_df.drop(["Nap_Dur", "Window_Conf"], axis=1)

    # calculate time of day in decimal hours of each event (asleep & wake)
    garmin_df["Bed_ToD"] = garmin_df["Bed_Time"].dt.hour + garmin_df["Bed_Time"].dt.minute/60
    garmin_df["Bed_ToD"] -= 24*(garmin_df["Bed_ToD"] > 12) # make PM bed times negative
    garmin_df["Wake_ToD"] = garmin_df["Wake_Time"].dt.hour + garmin_df["Wake_Time"].dt.minute/60

    # read & wrangle old microsoft sleep data
    ms2015_df = pd.read_csv(proj_path + "data/Activity_Summary_20150101_20151231.csv")
    ms2016_df = pd.read_csv(proj_path + "data/Activity_Summary_20160101_20161231.csv")
    ms2017_df = pd.read_csv(proj_path + "data/Activity_Summary_20170101_20171231.csv")
    ms_df = ms2015_df.append(ms2016_df).append(ms2017_df, sort=True). \
        query("Event_Type == 'Sleep'")
    ms2_df = pd.DataFrame()

    # create microsoft dataframe which mimics the garmin dataframe
    ms2_df["Prev_Day"] = pd.to_datetime(ms_df["Date"])
    ms2_df["Bed_Time"] = pd.to_datetime(ms_df["Start_Time"]). \
        dt.tz_localize("US/Eastern", ambiguous="NaT")
    for i_row in range(len(ms2_df)-1): 
        # fell asleep after midnght, adjust Prev_Day back 1 day
        if ms2_df.iloc[i_row, 1].hour < 12:
            ms2_df.iloc[i_row, 0] -= datetime.timedelta(days=1)
    ms2_df["Wake_Time"] = pd.to_datetime(ms_df["Wake_Up_Time"]). \
        dt.tz_localize("US/Eastern", ambiguous="NaT")
    ms2_df["Light_Dur"] = pd.to_timedelta(ms_df["Seconds_Asleep_Light"], "seconds")
    ms2_df["Deep_Dur"] = pd.to_timedelta(ms_df["Seconds_Asleep_Restful"], "seconds")
    ms2_df["Total_Dur"] = pd.to_timedelta(ms_df["Seconds_Awake"], "seconds") \
                        + ms2_df["Light_Dur"] + ms2_df["Deep_Dur"]
    ms2_df["Bed_ToD"] = ms2_df["Bed_Time"].dt.hour \
                   + ms2_df["Bed_Time"].dt.minute/60
    ms2_df["Bed_ToD"] -= 24*(ms2_df["Bed_ToD"] > 12) # make PM bed times negative
    ms2_df["Wake_ToD"] = ms2_df["Wake_Time"].dt.hour \
                        + ms2_df["Wake_Time"].dt.minute/60
    brief_sleep_bool = ms2_df["Total_Dur"] < pd.Timedelta(4, unit="h")
    daytime_asleep_bool = (ms2_df["Bed_ToD"] > -3) | (ms2_df["Bed_ToD"] < 7)
    unknown_dur_bool = pd.isnull(ms2_df["Total_Dur"])
    nap_bool = brief_sleep_bool & daytime_asleep_bool
    ms3_df = ms2_df.loc[~nap_bool & ~unknown_dur_bool, :]

    # combine garmin and microsoft data
    all_df = garmin_df.append(ms3_df, sort=True)
    all_df["Prev_Day"] = pd.to_datetime(all_df["Prev_Day"])

    # fill in missing days between first and last days in combined dataset
    complete_dates_ls = daterange(min(all_df["Prev_Day"]), max(all_df["Prev_Day"]))
    missing_dates_ls = np.setdiff1d(complete_dates_ls, all_df["Prev_Day"].dt.date)
    for date in missing_dates_ls:
        all_df.loc[len(all_df)] = [pd.NaT, pd.NaT, np.NAN, pd.NaT, pd.NaT, date, \
                                    pd.NaT, pd.NaT, np.NAN]
    all_df = all_df.sort_values("Prev_Day").reset_index(drop=True)

    # split data into an event dataframe (with start and stop datetime info) 
    # and sleep description dataframe, with durations, etc.  Each sleep
    # session will be tracked with a new ID in case info needs to be joined again
    all_df["Sleep_Session_ID"] = list(range(len(all_df)))
    all_descr_df = all_df.loc[:, ["Sleep_Session_ID", "Prev_Day", "Awake_Dur",
                                "Light_Dur", "Deep_Dur", "Total_Dur"]]
    all_event_df = all_df.loc[:, ["Sleep_Session_ID", "Prev_Day", "Bed_Time",
                                "Bed_ToD", "Wake_Time", "Wake_ToD"]]

    # add features to descr_df: day of week, year,  is_holiday, is_workday
    all_descr_df["Year"] = all_descr_df["Prev_Day"].dt.year
    all_descr_df["Day"] = all_descr_df["Prev_Day"].dt.weekday.astype(str)
    day_map = {
        "0": "Monday",
        "1": "Tuesday",
        "2": "Wednesday",
        "3": "Thursday",
        "4": "Friday",
        "5": "Saturday",
        "6": "Sunday"
    }
    all_descr_df["Day"] = all_descr_df["Day"].map(day_map).astype("category")

    # Get standard US holidays
    holidays = calendar().holidays(start=min(all_descr_df["Prev_Day"]),
                                end=max(all_descr_df["Prev_Day"]))

    # add day after thanksgiving
    nov_holidays = holidays[holidays.month == 11]
    tg_holidays = nov_holidays[nov_holidays.day > 20]
    bf_holidays = tg_holidays + datetime.timedelta(days=1)
    holidays = holidays.append(bf_holidays)

    # remove presidents day (feb), columbus day (oct), veterans day (nov)
    holidays = holidays[(holidays.month != 2) & (holidays.month != 10)]
    holidays = holidays[~ ((holidays.month == 11) & (holidays.day < 20))]
    holidays_prev_day = holidays - datetime.timedelta(days=1)
    all_descr_df["Is_Holiday"] = all_descr_df["Prev_Day"].isin(holidays)
    is_weekend_bool = all_descr_df["Day"].isin(["Friday", "Saturday"])
    all_descr_df.loc[is_weekend_bool, "Is_Holiday"] = False

    # add christmas eve & all days after christmas
    christmas_holidays = holidays[holidays.month == 12]
    vacay = christmas_holidays - datetime.timedelta(days=1)
    for n in range(1, 7):
        days_ls = christmas_holidays + datetime.timedelta(days=n)
        vacay = vacay.append(days_ls)
    
    # adding current layoff
    end_dt_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    start_dt_date = datetime.date(2019, 10, 28)
    layoff_days = ((end_dt_date - start_dt_date) + datetime.timedelta(days=1)).days
    layoff_ls = [start_dt_date + datetime.timedelta(days=x) for x in range(layoff_days)]
    layoff_series = pd.date_range(start_dt_date, end_dt_date)
    vacay = vacay.append(layoff_series)

    # if not in vacay list, assume the day was a work day
    all_descr_df["Is_Workday"] = ~ ((all_descr_df["Is_Holiday"]) |
                                    (all_descr_df["Prev_Day"].isin(vacay)))
    all_descr_df.loc[is_weekend_bool, "Is_Workday"] = False

    # reshape event df so each event is a separate row
    all_event_dt_df = pd.melt(all_df, id_vars=["Sleep_Session_ID", "Prev_Day"], 
                            value_vars=["Bed_Time", "Wake_Time"],
                            value_name="DateTime", var_name="Event")
    all_event_dt_df = all_event_dt_df.replace("Bed_Time", "Fell Asleep"). \
                    replace("Wake_Time", "Woke Up")
    all_event_tod_df = pd.melt(all_df, id_vars=["Sleep_Session_ID", "Prev_Day"], 
                            value_vars=["Bed_ToD", "Wake_ToD"], 
                            value_name="ToD", var_name="Event")
    all_event_tod_df = all_event_tod_df.replace("Bed_ToD", "Fell Asleep"). \
                    replace("Wake_ToD", "Woke Up")
    all_event_df = pd.merge(all_event_dt_df, all_event_tod_df). \
        sort_values(["Sleep_Session_ID", "Event"]).reset_index(drop=True)
    all_event_df["DateTimeStr"] = all_event_df["DateTime"]. \
        dt.strftime('%B %d, %Y, %r')

    # write cleaned dataframes to project dir
    all_descr_df.to_pickle(proj_path + all_descr_results_fn)
    all_event_df.to_pickle(proj_path + all_event_results_fn)

    msg = "Data has been transformed and merged with previous dataset"
    return [msg, all_descr_df, all_event_df, complete_dates_ls]

def step4(complete_dates_ls):

    # get archived sunrise/sunset dataframe
    if isfile(proj_path + sun_pkl_fn):
        sun_df = pd.read_pickle(proj_path + sun_pkl_fn)
    else:
        sun_df = pd.DataFrame(columns=["Date", "Sunrise", "Sunrise_ToD",
                                    "Sunset", "Sunset_ToD"])
    # build new list of dates which omits dates already obtained
    new_sun_dates_ls = []
    if len(sun_df) > 0:
        for n in complete_dates_ls:
            if not sun_df.Date.isin([n]).any(axis=None):
                new_sun_dates_ls.append(n)
    else:
        new_sun_dates_ls = complete_dates_ls
    
    if len(new_sun_dates_ls) > 0:

        # get sunrise and sunset times for each date
        for i, w_date in enumerate(new_sun_dates_ls):

            # requestting sunrise & sunset times from https://sunrise-sunset.org/api
            weather_params = {
                "lat": sun_lat,
                "lng": sun_lon,
                "date": w_date.strftime(format="%Y-%m-%d"),
                "formatted": 1
            }
            response = requests.get("https://api.sunrise-sunset.org/json",
                                    params=weather_params)
            if response.status_code != 200:
                print("RESPONSE ERROR RECEIVED:")
                print('Status code: %d' % response.status_code)
                response_dict = json.loads(response.content.decode('UTF-8'))
                print('Content: %s' % response_dict["status"])
                raise Exception
            else:
                sun_json = json.loads(response.text)

                # extract times of day in UTC TZ from from response
                sunrise = datetime.datetime.strptime(sun_json["results"]["sunrise"], "%I:%M:%S %p") #YMD are omitted from json
                sunrise = sunrise.replace(year=w_date.year, month=w_date.month, day=w_date.day) #update with actual YMD
                sunset = datetime.datetime.strptime(sun_json["results"]["sunset"], "%I:%M:%S %p")
                sunset = sunset.replace(year=w_date.year, month=w_date.month, day=w_date.day)

                # localize time to EDT
                UTC_tz = pytz.timezone("UTC")
                EDT_tz = pytz.timezone(local_tz)
                sunrise = UTC_tz.localize(sunrise).astimezone(EDT_tz)
                sunset = UTC_tz.localize(sunset).astimezone(EDT_tz)

                # calculate time of day in hours from (-12, 12]
                sunrise_tod = sunrise.hour + sunrise.minute/60
                sunrise_tod -= 24*(sunrise_tod > 12)  # make PM times negative
                sunset_tod = sunset.hour + sunset.minute/60
                sunset_tod -= 24*(sunset_tod > 12)  # make PM times negative

                # add row to df
                sun_df.loc[len(sun_df)] = [w_date, sunrise, sunrise_tod, sunset, sunset_tod]

    # this df takes along to make, so avoid rebuilding it
    sun_df.to_pickle(proj_path + sun_pkl_fn)

    msg = "New sunrise and sunset data has been downloaded"
    return [msg, sun_df]