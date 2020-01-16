import pandas as pd
import datetime as dt

trim_year = 2019
trim_month = 12
trim_day = 6
trim_date = dt.datetime(trim_year, trim_month, trim_day)

sleep_descr_df = pd.read_pickle("data_backup/all_sleep_descr_df.pkl")
sleep_descr_df_trim = sleep_descr_df[sleep_descr_df.Prev_Day <= trim_date]
sleep_descr_df_trim.to_pickle("data/all_sleep_descr_df.pkl")

sleep_event_df = pd.read_pickle("data_backup/all_sleep_event_df.pkl")
sleep_event_df_trim = sleep_event_df[sleep_event_df.Prev_Day <= trim_date]
sleep_event_df_trim.to_pickle("data/all_sleep_event_df.pkl")

sun_df = pd.read_pickle("data_backup/sun_df.pkl")
sun_df_trim = sun_df[sun_df.Date <= trim_date]
sun_df_trim.to_pickle("data/sun_df.pkl")

garmin_df = pd.read_pickle("data_backup/garmin_sleep_df.pkl")
garmin_df_trim = garmin_df[garmin_df.Prev_Day <= dt.date(trim_year, trim_month, trim_day)]
garmin_df_trim.to_pickle("data/garmin_sleep_df.pkl")