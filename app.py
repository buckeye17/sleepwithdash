'''
This Dash app can run locally on a Windows machine or can be deployed
to a Heroku server.  It reads data in pandas dataframe format, stored
as pickle files.

The layout of this file is:
1) All imports
2) User input variables as global variables
3) Dash web elements layout
4) Callbacks defining how user actions alter the app content
'''
import os
import datetime as dt
import numpy as np
import pandas as pd
from matplotlib.cm import get_cmap as mpl_cmap
from statsmodels.nonparametric.smoothers_lowess import lowess
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from plotly import subplots
from plotly import graph_objects as go

# setup global variables
proj_path = ""
if os.name == "nt":
    # running on my local Windows machine
    ENV = "local"
else:
    # running on heroku server
    ENV = "heroku"

if ENV == "local":
    import os
    os.chdir("C:/Users/adiad/Anaconda3/envs/SleepApp/sleep_app/")

# this local module must be imported after navigating to the project root dir
import update_garmin_sleep as garmin_get

# set graphic elements & color palette
sleep_logo = "static/moon-white.png"
sun_rgba = list(mpl_cmap("viridis")(0.999)[:3]) + [1] # appending opacity
sun_fill_color = "rgba" + str(tuple(sun_rgba))
woke_up_color = "rgb" + str(mpl_cmap("viridis")(0.5)[:3])
woke_up_dark_color = "rgb" + str(mpl_cmap("viridis")(0.2)[:3])
fell_asleep_color = "rgb" + str(mpl_cmap("viridis")(0.8)[:3])
fell_asleep_dark_color = "rgb" + str(mpl_cmap("viridis")(0.7)[:3])
invis = "rgba(0,0,0,0)"

external_stylesheets = [dbc.themes.LITERA]

# dash instantiation
app = dash.Dash(__name__, external_stylesheets=external_stylesheets, assets_folder='assets')
server = app.server

# code layout
# web page layout is constructed in pieces to keep nested function levels within sane limits
# smallest pieces of layout are defined first, later pieces wrap the earlier pieces

# define 2 rows of filter controls for overview tab
# row 1: range slider to control x-axis range (dates)
# row 2: toggle buttons to filter different types of days
overview_filter_rows = [

    # date range slider filter
    dbc.Row([
        dbc.Col(
            html.Div("Date Range:"), width=2, style={'textAlign': 'right'}
        ),
        dbc.Col(html.Div([
            dcc.RangeSlider(
                id='date-range-slider',
                step=1,
                pushable=True
            )
        ]), width=6, style={'margin-top':10})
    ], style={'margin-bottom': 10, 'margin-top': 5}),

    # filter buttons for types of days
    dbc.Row([
        dbc.Col(
            html.Div("Days:"), width=2, style={'textAlign': 'right', 'margin-top':5}
        ),
        dbc.Col(html.Div([
            dbc.ButtonGroup(
                [dbc.Button(
                    'Monday',
                    id='mon-filter',
                    active=False
                ), 
                dbc.Button(
                    'Tuesday',
                    id='tue-filter',
                    active=False
                ),
                dbc.Button(
                    'Wednesday',
                    id='wed-filter',
                    active=False
                ),
                dbc.Button(
                    'Thursday',
                    id='thu-filter',
                    active=False
                ),
                dbc.Button(
                    'Friday',
                    id='fri-filter',
                    active=False
                ),
                dbc.Button(
                    'Saturday',
                    id='sat-filter',
                    active=False
                ),
                dbc.Button(
                    'Sunday',
                    id='sun-filter',
                    active=False
                )]
            )
        ]), width=7),
        dbc.Col(html.Div([
            dbc.ButtonGroup(
                [dbc.Button(
                    'Work nights',
                    id='work-nights-filter',
                    active=False
                ), 
                dbc.Button(
                    'Off nights*',
                    id='off-nights-filter',
                    active=False
                ),
                dbc.Tooltip(
                    "Off nights include weekends, holidays and known PTO",
                    target="off-nights-filter",
                )]
            )
        ]), width=3)
    ])
]

# define 1 row of filter controls for annual tab
# row 2: toggle buttons to filter different types of days
annual_filter_rows = [dbc.Row([
    dbc.Col(
        html.Div("Days:"), width=2, style={'textAlign': 'right', 'margin-top':5}
    ),
    dbc.Col(html.Div([
        dbc.ButtonGroup(
            [dbc.Button(
                'Monday',
                id='mon-filter-annual',
                active=False
            ), 
            dbc.Button(
                'Tuesday',
                id='tue-filter-annual',
                active=False
            ),
            dbc.Button(
                'Wednesday',
                id='wed-filter-annual',
                active=False
            ),
            dbc.Button(
                'Thursday',
                id='thu-filter-annual',
                active=False
            ),
            dbc.Button(
                'Friday',
                id='fri-filter-annual',
                active=False
            ),
            dbc.Button(
                'Saturday',
                id='sat-filter-annual',
                active=False
            ),
            dbc.Button(
                'Sunday',
                id='sun-filter-annual',
                active=False
            )]
        )
    ]), width=7),
    dbc.Col(html.Div([
        dbc.ButtonGroup(
            [dbc.Button(
                'Work nights',
                id='work-nights-filter-annual',
                active=False
            ), 
            dbc.Button(
                'Off nights*',
                id='off-nights-filter-annual',
                active=False
            ),
            dbc.Tooltip(
                "Off nights include weekends, holidays and known PTO",
                target="off-nights-filter-annual",
            )]
        )
    ]), width=3)
], style={'margin-top': 10})]

# wrap filter controls for overview tab view with collapse/hide capability
overview_filter_wrap = html.Div([
    dbc.Row([
        dbc.Col(dbc.Button(
            "Filters",
            id="overview-collapse-filters-btn",
        ), width=2, style={'textAlign': 'right'}),
        dbc.Col(dbc.Button(
            "Sync Data",
            id="overview-sync-data-btn",
        ), width=2)],
    justify="start"),
    dbc.Collapse(
        overview_filter_rows,
        id="overview-filters",
    )
], style={"margin-left": 10, "margin-top": 10})

# wrap filter controls for annual tab view with collapse/hide capability
annual_filter_wrap = html.Div([
    dbc.Row([
        dbc.Col(dbc.Button(
            "Filters",
            id="annual-collapse-filters-btn",
        ), width=2, style={'textAlign': 'right'}),
        dbc.Col(dbc.Button(
            "Sync Data",
            id="annual-sync-data-btn",
        ), width=2)],
    justify="start"),
        dbc.Collapse(
            annual_filter_rows,
            id="annual-filters",
        )
    ], style={"margin-left": 10, "margin-top": 10, "margin-bottom": 10})

# make a navbar dropdown extension
dropdown_menu_items = dbc.DropdownMenu(
    children=[
        dbc.DropdownMenuItem("Discussion of this App", href="https://buckeye17.github.io/Sleep-Dashboard/"),
        dbc.DropdownMenuItem("About the Author", href="https://buckeye17.github.io/about/"),
        dbc.DropdownMenuItem("LinkedIn Profile", href="https://www.linkedin.com/in/chris-raper/"),
        dbc.DropdownMenuItem("Github Repo", href="https://github.com/buckeye17/sleepwithdash"),
        dbc.DropdownMenuItem("plotly|Dash", href="https://plot.ly/dash/")
    ],
    nav=True,
    in_navbar=True,
    label="Menu",
)

# define overall app layout
app.layout = html.Div([

    # Banner/header block
    dbc.Navbar(
        dbc.Container([

            # left side of navbar: logo & app name
            html.A(
                # Use row and col to control vertical alignment of logo / brand
                dbc.Row(
                    [
                        dbc.Col(html.Img(src=sleep_logo, height="30px")),
                        dbc.Col(dbc.NavbarBrand([
                            "Sleep Dashboard", 
                            html.Br(), 
                            html.Div("written by Chris Raper", style={"fontSize": "small"})
                        ], className="ml-2")),
                    ],
                    align="center", no_gutters=True, className="ml-2",
                ),
                href="#",
            ),

            # right side of navbar: nav links & menu
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse(
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("My Portfolio", href="https://buckeye17.github.io/")),
                    dropdown_menu_items
                ], className="ml-auto", navbar=True),
                id="navbar-collapse", navbar=True,
            ),
        ]),
        color="primary",
        dark=True
    ),

    # define modal which will print progress while syncing with Garmin
    dbc.Modal([
        # these hidden divs enable chaining of callbacks while providing modal updates at each stage
        html.Div(id="sync-started", style={"display": "none"}),
        html.Div(False, id="sync-finished", style={"display": "none"}),
        dbc.ModalHeader("Sync Progress"),
        dbc.ModalBody([
            html.Div([dbc.Progress(value=3, max=5, id="sync-progress-bar"), #, style={"height": "3px"}
            dcc.Interval(id="progress-poll", interval=1*1000, n_intervals=0)]),
            html.Div(id="sync-step-0"),
            html.Div(id="sync-step-1"),
            html.Div(id="sync-step-2"),
            html.Div(id="sync-step-3"),
            html.Div(id="sync-step-4"),
            html.Div(id="sync-step-5"),
            html.Div(id="sync-step-6"),
        ], id="sync-data-modal-body"),
        dbc.ModalFooter(
            dbc.Button("Close", id="sync-data-modal-close", 
                    className="ml-auto", disabled=True)
        )
    ], id="sync-data-modal", size="md", is_open=False),

    # define tabs which provide different perspectives on data
    dbc.Tabs([

        # overview tab
        dbc.Tab([
            overview_filter_wrap,
            dbc.Row(dbc.Col(html.Div([dcc.Loading(dcc.Graph(id="overview-scatter-plot"), type="cube")]))),
            dbc.Row(dbc.Col(html.Div([dcc.Markdown('''
                Sunrise and sunset data was obtained from: [https://sunrise-sunset.org/api](https://sunrise-sunset.org/api)
            ''', style={"fontSize": "small", "textAlign": "center"})])))
        ], label="Overview"),

        # annual tabe
        dbc.Tab([
            annual_filter_wrap,

            # make plotted-variable picker
            dbc.Row([
                dbc.Col(html.Div("Plotted Sleep Variable:"), width=2, style={'textAlign': 'right'}),
                dbc.Col(dbc.Select(
                    id="annual-plot-picker",
                    options=[
                        {"label": "Fell Asleep", "value": "fell asleep"},
                        {"label": "Woke Up", "value": "woke up"},
                        {"label": "Duration", "value": "dur"},
                    ],
                    bs_size="sm",
                    value="fell asleep"
                ), width=2),
            ], justify="center"),
            dbc.Row(dbc.Col(html.Div([dcc.Loading(dcc.Graph(id="annual-scatter-plot"), type="cube")]))),
            dbc.Row(dbc.Col(html.Div([dcc.Markdown('''
                This plot shows the average sunrise or sunset time per date, spanning all dates in sleep dataset  
                Sunrise and sunset data was obtained from: [https://sunrise-sunset.org/api](https://sunrise-sunset.org/api)
            ''', style={"fontSize": "small", "textAlign": "center", "margin-top": 10})]))),
        ], label="Annual View")
    ])
])

# the remainder of this code defines callback functions

# add callback for toggling the right nav menu collapse on small screens
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


# define the filter collapse functions for the overview & annual tabs
@app.callback(
    [Output("overview-filters", "is_open"),
     Output("overview-collapse-filters-btn", "color"),
     Output("overview-collapse-filters-btn", "children")],
    [Input("overview-collapse-filters-btn", "n_clicks")],
)
def toggle_filters_collapse(n, color_opts=['secondary', 'primary']):
    if n is None:
        n = 0
    if n % 2 == 1:
        return [True, color_opts[1], "Hide Plot Filters"]
    else:
        return [False, color_opts[0], "Show Plot Filters"]


@app.callback(
    [Output("annual-filters", "is_open"),
     Output("annual-collapse-filters-btn", "color"),
     Output("annual-collapse-filters-btn", "children")],
    [Input("annual-collapse-filters-btn", "n_clicks")],
)
def toggle_filters_collapse(n, color_opts=['secondary', 'primary']):
    if n is None:
        n = 0
    if n % 2 == 1:
        return [True, color_opts[1], "Hide Plot Filters"]
    else:
        return [False, color_opts[0], "Show Plot Filters"]


# toggle open state of sync modal box
@app.callback(
    [Output("sync-data-modal", "is_open")],
    [Input("overview-sync-data-btn", "n_clicks"),
     Input("annual-sync-data-btn", "n_clicks"),
     Input("sync-data-modal-close", "n_clicks")],
    [State("sync-data-modal", "is_open")]
)
def toggle_modal(sync_over_clicks, sync_annual_clicks, modal_close_clicks,
                 modal_is_open: bool):
    if (sync_over_clicks is None) & (sync_annual_clicks is None) & \
       (modal_close_clicks is None):
        return [False]
    else:
        return [not modal_is_open]


# this call back responds to all buttons related to data syncing
@app.callback(
    [Output("sync-step-0", "children"),
     Output("sync-started", "children")],
    [Input("overview-sync-data-btn", "n_clicks"),
     Input("annual-sync-data-btn", "n_clicks")],
    [State("sync-data-modal", "is_open"),
     State("sync-finished", "children")]
)
def sync_data(sync_overview_clicks, sync_annual_clicks, \
              sync_open_bool, sync_finished: bool):
    if (sync_overview_clicks is None) & (sync_annual_clicks is None):
        # no buttons have been clicked yet
        step0_msg = None
        sync_started = False
    else:
        sync_started = True
        if sync_finished:
            # don't attempt any more syncs
            step0_msg = None
        else:
            step0_msg = html.B("Completed steps:")
    return [step0_msg, sync_started]


# step 0 of data sync process
nights_df = pd.DataFrame() # data to be used in subsequent sync functions
new_req_dates_ls = [] # data to be used in subsequent sync functions
@app.callback(
    [Output("sync-step-1", "children")],
    [Input("sync-step-0", "children")],
    [State("sync-finished", "children"),
     State("sync-step-1", "children")]
)
def do_sync_step0(msg, sync_already_finished: bool, out_msg):
    global nights_df, new_req_dates_ls
    if sync_already_finished == True:
        msg = out_msg
    else:
        if msg is not None:
            [msg, nights_df, new_req_dates_ls] = garmin_get.step0()
    return [msg]


# step 1 of data sync process
request = {} # data to be used in subsequent sync functions
@app.callback(
    [Output("sync-step-2", "children")],
    [Input("sync-step-1", "children")],
    [State("sync-finished", "children"),
     State("sync-step-2", "children")]
)
def do_sync_step1(msg, sync_already_finished: bool, out_msg):
    global request
    if sync_already_finished == True:
        msg = out_msg
    else:
        if (msg is not None):
            if sync_already_finished:
                msg = None
            else:
                [msg, request] = garmin_get.step1()
    return [msg]


# step 2 of data sync process
data_json = {} # data to be used in subsequent sync functions
@app.callback(
    [Output("sync-step-3", "children")],
    [Input("sync-step-2", "children")],
    [State("sync-finished", "children"),
     State("sync-step-3", "children")]
)
def do_sync_step2(msg, sync_already_finished: bool, out_msg):
    global data_json
    if sync_already_finished == True:
        msg = out_msg
    else:
        if msg is not None:
            [msg, data_json] = garmin_get.step2(request, new_req_dates_ls)
            msg = "Downloaded new data from Garmin" 
    return [msg]


# step 3 of data sync process
complete_dates_ls = [] # data to be used in subsequent sync functions
@app.callback(
    [Output("sync-step-4", "children")],
    [Input("sync-step-3", "children")],
    [State("sync-finished", "children"),
     State("sync-step-4", "children")]
)
def do_sync_step3(msg, sync_already_finished: bool, out_msg):
    global complete_dates_ls

    if sync_already_finished == True:
        msg = out_msg
    else:
        if msg is not None:
            # since plotting data is mutable (subject to adding new data)
            # this data is read from disk, ensuring all callbacks are accessing the same data
            sleep_descr_df = pd.read_pickle(proj_path + "data/all_sleep_descr_df.pkl")

            # dataframe files on disk will be overwritten in step3()
            # function with new dataframes
            [msg, new_sleep_descr_df, new_sleep_event_df, complete_dates_ls] = \
                garmin_get.step3(nights_df, data_json, new_req_dates_ls)
            new_nights = len(new_sleep_descr_df) - len(sleep_descr_df)
            msg = str(new_nights) + " night(s) were added to the sleep dataset"
        
    return [msg]


# step 4 of data sync process
@app.callback(
    [Output("sync-step-5", "children")],
    [Input("sync-step-4", "children")],
    [State("sync-finished", "children"),
     State("sync-step-5", "children")]
)
def do_sync_step4(msg, sync_already_finished: bool, out_msg):
    if sync_already_finished == True:
        msg = out_msg
    else:
        if msg is not None:
            # dataframe file on disk will be overwritten in step4()
            # function with new dataframe
            [msg, new_sun_df] = garmin_get.step4(complete_dates_ls)
            msg = "Updated sunrise/sunset dataset"
    return [msg]


# propagate data sync updates back to app main elements
@app.callback(
    [Output("sync-step-6", "children"),
     Output("sync-finished", "children"),
     Output("sync-data-modal-close", "disabled"),
     Output("date-range-slider", "min"),
     Output("date-range-slider", "max"),
     Output("date-range-slider", "value"),
     Output("date-range-slider", "marks")],
    [Input("sync-step-5", "children")],
    [State("sync-finished", "children"),
     State("sync-started", "children"),
     State("sync-step-1", "children"),
     State("date-range-slider", "value"),
     State("sync-step-6", "children")]
)
def do_sync_step4(msg, sync_already_finished: bool, sync_started: bool, step1_msg, \
                  overview_slider_vals, out_msg):
    
    # since plotting data is mutable (subject to adding new data)
    # this data is read from disk, ensuring all callbacks are accessing the same data
    sleep_descr_df = pd.read_pickle(proj_path + "data/all_sleep_descr_df.pkl")

    # slider range
    overview_slider_min = 0
    overview_slider_max = len(sleep_descr_df) - 1

    # build a dict of Jan. 1 of every year in date range to use as marks
    prev_day_ls = sleep_descr_df.Prev_Day.to_list()
    year_ls = np.unique(sleep_descr_df.Prev_Day.dt.year.to_list())
    year_ls = year_ls[1:]
    
    # make lists for keys and values of marks dict
    mark_dict_keys = [prev_day_ls.index(dt.datetime(year, 1, 1)) for year in year_ls]
    mark_dict_vals = [{"label": "1/1/" + str(year)} for year in year_ls]

    # bring lists together into marks dict
    # each entry in marks dict will resemble:
    # prev_day_ls.index(dt.datetime(2016, 1, 1)): {'label': '1/1/2016'}
    mark_dict_tup = zip(mark_dict_keys, mark_dict_vals)
    overview_slider_marks={
        key: value for (key, value) in mark_dict_tup
    }

    # always move right slider to max position, but not left slider
    if overview_slider_vals is None:
        # slider values and marks need to be set
        overview_slider_vals = [0, overview_slider_max]

    else:
        overview_slider_vals = [overview_slider_vals[0], overview_slider_max]

    # prevent subsequent syncs if sync has already been successful
    if (sync_already_finished != True) & (msg is not None):
        msg = "Finished syncing"
        finished_bool = True
    else:
        msg = out_msg
        finished_bool = sync_already_finished

    # enable close button once first sync is complete, and for all subsequent
    # sync attempts
    close_btn_disabled = False     
    if (sync_started != True) & (~ finished_bool):
        close_btn_disabled = True

    return [msg, finished_bool, close_btn_disabled, overview_slider_min, \
            overview_slider_max, overview_slider_vals, overview_slider_marks]


# this callback polls the status of the sync steps and updates the progress bar
@app.callback(
    [Output("sync-progress-bar", "value")],
    [Input("progress-poll", "n_intervals")],
    [State("sync-step-1", "children"),
     State("sync-step-2", "children"),
     State("sync-step-3", "children"),
     State("sync-step-4", "children"),
     State("sync-step-5", "children"),
     State("sync-finished", "children")]
)
def update_progress_bar(n_int, step1_msg, step2_msg, step3_msg, step4_msg, \
                        step5_msg, sync_already_finished: bool):
    msg_ls = [step1_msg, step2_msg, step3_msg, step4_msg, step5_msg]
    if (sync_already_finished == True) | \
       (step1_msg == "Archived data is up to date, no new data is available."):
        prog_val = len(msg_ls) # 100%
    else:
        prog_vals_ls = [1 for msg in msg_ls if msg is not None]
        prog_val = len(prog_vals_ls)
    return [prog_val]


# define functions used in all graph update callbacks

# this function interprets the number of clicks on a button
# as odd or even, then provides the corresponding boolean
# and button color values, where color_opts are the colors
# for false and true respectively
def react_clicks(n, color_opts=['light', 'primary']):
    if n is None:
        n = 0
    mask = n % 2 == 0
    btn_color = color_opts[mask]
    return mask, btn_color

# react UI elements for types of days
def react_tod_clicks(wn_clicks, offn_clicks):
    wn_mask, wn_color = react_clicks(wn_clicks)
    offn_mask, offn_color = react_clicks(offn_clicks)
    tod_mask = [wn_mask, offn_mask]
    tod_vals = [True, False]
    tod_filter = [val for i, val in enumerate(tod_vals) if tod_mask[i]]
    return [wn_color, offn_color, tod_filter]


# react UI elements for days of week
def react_dow_clicks(mon_clicks, tue_clicks, wed_clicks, thu_clicks,
                     fri_clicks, sat_clicks, sun_clicks):
    mon_mask, mon_color = react_clicks(mon_clicks)
    tue_mask, tue_color = react_clicks(tue_clicks)
    wed_mask, wed_color = react_clicks(wed_clicks)
    thu_mask, thu_color = react_clicks(thu_clicks)
    fri_mask, fri_color = react_clicks(fri_clicks)
    sat_mask, sat_color = react_clicks(sat_clicks)
    sun_mask, sun_color = react_clicks(sun_clicks)
    dow_mask = [mon_mask, tue_mask, wed_mask, thu_mask,
                fri_mask, sat_mask, sun_mask]
    dow_vals = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                'Friday', 'Saturday', 'Sunday']
    dow_filter = [val for i, val in enumerate(dow_vals) if dow_mask[i]]
    return [mon_color, tue_color, wed_color, thu_color, fri_color,
            sat_color, sun_color, dow_filter]



# define all of the overview filters functionality and corresponding graph
@app.callback(
    [Output('overview-scatter-plot', 'figure'),
     Output('mon-filter', 'color'),
     Output('tue-filter', 'color'),
     Output('wed-filter', 'color'),
     Output('thu-filter', 'color'),
     Output('fri-filter', 'color'),
     Output('sat-filter', 'color'),
     Output('sun-filter', 'color'),
     Output('work-nights-filter', 'color'),
     Output('off-nights-filter', 'color')],
    [Input('date-range-slider', 'value'),
     Input('mon-filter', 'n_clicks'),
     Input('tue-filter', 'n_clicks'),
     Input('wed-filter', 'n_clicks'),
     Input('thu-filter', 'n_clicks'),
     Input('fri-filter', 'n_clicks'),
     Input('sat-filter', 'n_clicks'),
     Input('sun-filter', 'n_clicks'),
     Input('work-nights-filter', 'n_clicks'),
     Input('off-nights-filter', 'n_clicks')],
    [State("date-range-slider", "max")]
)
def update_graph(date_range, mon_clicks, tue_clicks, wed_clicks,
                 thu_clicks, fri_clicks, sat_clicks, sun_clicks,
                 wn_clicks, offn_clicks, max_date):
    
    # since plotting data is mutable (subject to adding new data)
    # this data is read from disk, ensuring all callbacks are accessing the same data
    sleep_descr_df = pd.read_pickle(proj_path + "data/all_sleep_descr_df.pkl")
    sleep_event_df = pd.read_pickle(proj_path + "data/all_sleep_event_df.pkl")
    sun_df = pd.read_pickle(proj_path + "data/sun_df.pkl")

    # interpret click values for updating UI & data filters
    [wn_color, offn_color, tod_filter] = react_tod_clicks(wn_clicks, offn_clicks)
    [mon_color, tue_color, wed_color, thu_color, fri_color, sat_color, sun_color, dow_filter] = \
        react_dow_clicks(mon_clicks, tue_clicks, wed_clicks, thu_clicks, fri_clicks, sat_clicks, sun_clicks)

    # filter date range using the row index
    if date_range is None:
        # date range slider hasn't initialized yet, so ignore it
        mask_df = sleep_descr_df
    else:
        mask_df = sleep_descr_df.iloc[date_range[0]:date_range[1],:]
    
    # filter types of day by getting sleep session IDs which meet filter criteria
    mask_df = mask_df[(mask_df["Day"].isin(dow_filter)) & 
                        (mask_df["Is_Workday"].isin(tod_filter))]
    
    # generate filtered dataframe
    data_df = sleep_event_df[sleep_event_df["Sleep_Session_ID"].isin(mask_df["Sleep_Session_ID"])]

    # manual y-axes limits
    y_dur_range = [3, 12]
    y_tod_range = [-4, 13]

    fig = subplots.make_subplots(rows=2, cols=2, column_widths=[0.85, 0.15], 
                                 row_heights=[0.6, 0.4], horizontal_spacing=0,
                                 vertical_spacing=0.03)

    # add sleep duration scatter plot
    fig.add_trace(go.Scatter(
        name="Sleep<br>Duration",
        x=mask_df.Prev_Day,
        y=mask_df.Total_Dur.dt.seconds/(60.*60),
        text=mask_df.Prev_Day.dt.strftime('%B %d, %Y'),
        hovertemplate="%{text}<br>Duration: %{y:.2f} hours",
        marker_color="gray",
        marker_line_width=0, 
        marker_size=6,
        mode="markers",
        opacity=0.5,
        showlegend=False
    ), row=2, col=1)

    # add dummy trace to format "Sleep Duration" as single line in legend
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                             marker=dict(size=8, color='gray', opacity=0.7),
                             showlegend=True, name='Sleep Duration'), row=2, col=1)

    # add smooth signal line for duration
    mask_days = mask_df.Prev_Day - np.nanmin(mask_df.Prev_Day)
    fit_dur = lowess(mask_df.Total_Dur.dt.seconds/(60.*60), mask_days.dt.days,
                     is_sorted=True, frac=0.04, it=0)
    fig.add_trace(go.Scatter(
        name="Smoothed<br>Duration",
        x=min(mask_df.Prev_Day) + pd.to_timedelta(fit_dur[:,0], unit="D"),
        y=fit_dur[:,1],
        text=mask_df.Prev_Day.dt.strftime('%B %d, %Y'),
        hovertemplate="%{text}<br>Duration: %{y:.2f} hours",
        mode="lines",
        line=dict(
            color="gray",
            width=4
        ),
        opacity=1,
        showlegend=False
    ), row=2, col=1)

    # add histogram along y-axis (duration)
    fig.add_trace(go.Histogram(
        name="Duration<br>Histogram",
        y=mask_df.Total_Dur.dt.seconds/(60.*60),
        nbinsy=round((y_dur_range[1] - y_dur_range[0])*8),
        histnorm="percent",
        marker=dict(
            color="gray"
        ),
        showlegend=False
    ), row=2, col=2)

    # add sleep events scatter plot
    # first add sunrise/sunset background
    fig.add_trace(go.Scatter(
        name="Below Sunset",
        x=sun_df["Date"],
        y=[-17]*len(sun_df),
        hovertemplate=None,
        fillcolor=invis,
        fill="tonextx",
        mode="lines",
        marker_color=invis,
        marker_line_width=0,
        marker_size=0,
        line_color=invis,
        opacity=0,
        showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        name="Sunset",
        x=sun_df["Date"],
        y=sun_df["Sunset_ToD"],
        text=sun_df.Sunset.dt.strftime("%B %d, %r"),
        hovertemplate="%{text}",
        fillcolor=sun_fill_color,
        fill="tonextx",
        mode="lines",
        marker_color=sun_fill_color,
        marker_line_width=0,
        marker_size=0,
        line_color=sun_fill_color,
        opacity=1,
        showlegend=False
    ), row=1, col=1)

    # add daylight background
    fig.add_trace(go.Scatter(
        name="Sunrise",
        x=sun_df["Date"],
        y=sun_df["Sunrise_ToD"],
        text=sun_df.Sunrise.dt.strftime("%B %d, %r"),
        hovertemplate="%{text}",
        fillcolor=invis,
        fill="tozeroy",
        mode="lines",
        marker_color=invis,
        marker_line_width=0,
        marker_size=0,
        line_color=invis,
        opacity=0,
        showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        name="Above Sunrise",
        x=sun_df["Date"],
        y=[16]*len(sun_df),
        hovertemplate=None,
        fill="tonextx",
        fillcolor=sun_fill_color,
        mode="lines",
        marker_color=sun_fill_color,
        marker_line_width=0,
        marker_size=0,
        line_color=sun_fill_color,
        opacity=1,
        showlegend=False
    ), row=1, col=1)

    # add dummy trace to explain sunrise/sunset in legend
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                             marker=dict(size=8, color=sun_fill_color),
                             showlegend=True, name='Sun is Up'), row=1, col=1)

    # plot sleep event data
    fig.add_trace(go.Scatter(
        name="Fell Asleep",
        x=data_df.query('Event == "Fell Asleep"').Prev_Day,
        y=data_df.query('Event == "Fell Asleep"').ToD,
        text=data_df.query('Event == "Fell Asleep"').DateTimeStr,
        hovertemplate =
        "%{text}",
        marker_color=fell_asleep_color,
        marker_line_width=0, 
        marker_size=6,
        mode="markers",
        opacity=0.5,
        showlegend=False
    ), row=1, col=1)

    # add dummy trace to show larger marker in legend
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                             marker=dict(size=8, color=fell_asleep_color),
                             showlegend=True, name='Fell Asleep'), row=1, col=1)

    # add smooth signal line for falling asleep
    asleep_start_day = np.nanmin(data_df.query('Event == "Fell Asleep"').Prev_Day)
    asleep_days = data_df.query('Event == "Fell Asleep"').Prev_Day - asleep_start_day
    asleep_hours = data_df.query('Event == "Fell Asleep"').ToD
    fit_asleep = lowess(asleep_hours, asleep_days.dt.days, is_sorted=True, frac=0.04, it=0)
    fit_asleep_dt = asleep_start_day + pd.to_timedelta(fit_asleep[:,0], unit="days") + \
                    pd.to_timedelta(fit_asleep[:,1], unit="hours")
    fig.add_trace(go.Scatter(
        name="Smoothed<br>Asleep",
        x=min(data_df.Prev_Day) + pd.to_timedelta(fit_asleep[:,0], unit="D"),
        y=fit_asleep[:,1],
        text=fit_asleep_dt.strftime('%B %d, %Y %r'),
        hovertemplate="%{text}",
        mode="lines",
        line=dict(
            color=fell_asleep_color,
            width=4
        ),
        opacity=1,
        showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        name="Woke Up",
        x=data_df.query('Event == "Woke Up"').Prev_Day,
        y=data_df.query('Event == "Woke Up"').ToD,
        text=data_df.query('Event == "Woke Up"').DateTimeStr,
        hovertemplate="%{text}",
        marker_color=woke_up_color,
        marker_line_width=0, 
        marker_size=6,
        mode="markers",
        opacity=0.8,
        showlegend=False
    ), row=1, col=1)

    # add dummy trace to show larger marker in legend
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                             marker=dict(size=8, color=woke_up_color),
                             showlegend=True, name='Woke Up'), row=1, col=1)

    # add smooth signal line for waking up
    wake_start_day = np.nanmin(data_df.query('Event == "Woke Up"').Prev_Day)
    wake_days = data_df.query('Event == "Woke Up"').Prev_Day - asleep_start_day
    wake_hours = data_df.query('Event == "Woke Up"').ToD
    fit_wake = lowess(wake_hours, wake_days.dt.days, is_sorted=True, frac=0.04, it=0)
    fit_wake_dt = wake_start_day + pd.to_timedelta(fit_wake[:,0], unit="days") + \
                  pd.to_timedelta(fit_wake[:,1], unit="hours")
    fig.add_trace(go.Scatter(
        name="Smoothed<br>Woke Up",
        x=min(data_df.Prev_Day) + pd.to_timedelta(fit_wake[:,0], unit="D"),
        y=fit_wake[:,1],
        text=mask_df.Prev_Day.dt.strftime('%B %d, %Y'),
        hovertemplate=fit_wake_dt.strftime('%B %d, %Y %r'),
        mode="lines",
        line=dict(
            color=woke_up_dark_color,
            width=4
        ),
        opacity=1,
        showlegend=False
    ), row=1, col=1)

    # add histograms along y-axis (time of day)
    fig.add_trace(go.Histogram(
        name="Woke Up<br>Histogram",
        y=data_df.query('Event == "Woke Up"').ToD,
        histnorm="percent",
        marker=dict(
            color=woke_up_dark_color
        ),
        showlegend=False
    ), row=1, col=2)

    fig.add_trace(go.Histogram(
        name="Fell Asleep<br>Histogram",
        y=data_df.query('Event == "Fell Asleep"').ToD,
        histnorm="percent",
        marker=dict(
            color=fell_asleep_color
        ),
        showlegend=False
    ), row=1, col=2)

    # define all 4 x-axes
    fig.update_xaxes(row=1, col=1, zeroline=True, #dtick="M12", 
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        range=[min(mask_df["Prev_Day"]), max(mask_df["Prev_Day"])], showticklabels=False)
    
    fig.update_xaxes(row=1, col=2, zeroline=False, linecolor=invis, gridcolor=invis, 
        ticktext=[], tickvals=[], mirror=False)
    
    fig.update_xaxes(row=2, col=1, zeroline=True, #dtick="M12", 
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        range=[min(mask_df["Prev_Day"]), max(mask_df["Prev_Day"])])
    
    fig.update_xaxes(row=2, col=2, zeroline=False, linecolor=invis, gridcolor=invis, 
        ticktext=[], tickvals=[], mirror=False)
    
    # define all 4 y-axes
    fig.update_yaxes(row=1, col=1, zeroline=True, zerolinecolor="gray", zerolinewidth=0.5,
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        ticktext=["6 PM", "Midnight", "6 AM", "Noon"], tickvals=[-6, 0, 6, 12], 
        title_text="Event Time", range=y_tod_range)
    
    fig.update_yaxes(row=1, col=2, zeroline=False, linecolor=invis, gridcolor=invis, 
        mirror=False, ticktext=["", "", "", ""], tickvals=[-6, 0, 6, 12], range=y_tod_range)
    
    fig.update_yaxes(row=2, col=1, zeroline=True, zerolinecolor="gray", zerolinewidth=0.5,
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        title_text="Sleep Duration<br>(hours)", range=y_dur_range)
    
    fig.update_yaxes(row=2, col=2, zeroline=False, linecolor=invis, gridcolor=invis, 
        mirror=False, ticktext=["", "", "", ""], tickvals=[-6, 0, 6, 12],
        range=y_dur_range)

    # define overall layout and legend properties
    fig.update_layout(
        paper_bgcolor=invis,
        plot_bgcolor=invis,
        margin=go.layout.Margin(l=50, r=20, b=10, t=10),
        autosize=True,
        legend=go.layout.Legend(
            x=0,
            y=1.1,
            traceorder="reversed",
            font=dict(
                family="sans-serif",
                size=12,
                color="black"
            ),
            bgcolor="white",
            bordercolor="gray",
            borderwidth=0.5),
        legend_orientation="h")

    return [fig, mon_color, tue_color, wed_color, thu_color, \
            fri_color, sat_color, sun_color, wn_color, offn_color]



# define all of the annual filters functionality and corresponding graph
@app.callback(
    [Output('annual-scatter-plot', 'figure'),
     Output('mon-filter-annual', 'color'),
     Output('tue-filter-annual', 'color'),
     Output('wed-filter-annual', 'color'),
     Output('thu-filter-annual', 'color'),
     Output('fri-filter-annual', 'color'),
     Output('sat-filter-annual', 'color'),
     Output('sun-filter-annual', 'color'),
     Output('work-nights-filter-annual', 'color'),
     Output('off-nights-filter-annual', 'color')],
    [Input('annual-plot-picker', 'value'),
     Input('mon-filter-annual', 'n_clicks'),
     Input('tue-filter-annual', 'n_clicks'),
     Input('wed-filter-annual', 'n_clicks'),
     Input('thu-filter-annual', 'n_clicks'),
     Input('fri-filter-annual', 'n_clicks'),
     Input('sat-filter-annual', 'n_clicks'),
     Input('sun-filter-annual', 'n_clicks'),
     Input('work-nights-filter-annual', 'n_clicks'),
     Input('off-nights-filter-annual', 'n_clicks')]
)
def annual_update_graph(plot_picker, mon_clicks, tue_clicks, wed_clicks,
                        thu_clicks, fri_clicks, sat_clicks, sun_clicks,
                        wn_clicks, offn_clicks):
    
    # since plotting data is mutable (subject to adding new data)
    # this data is read from disk, ensuring all callbacks are accessing the same data
    sleep_descr_df = pd.read_pickle(proj_path + "data/all_sleep_descr_df.pkl")
    sleep_event_df = pd.read_pickle(proj_path + "data/all_sleep_event_df.pkl")
    sun_df = pd.read_pickle(proj_path + "data/sun_df.pkl")
    
    # filter out data with less than 100 days of data in a year
    years_cnt = sleep_descr_df["Year"].value_counts()
    years_ls = years_cnt[years_cnt > 100].index.to_list()

    # make viridis color levels for each year
    cmap_start = 0.1
    cmap_stop = 1
    cmap_ls = [cmap_start + x*(cmap_stop - cmap_start)/len(years_ls) for x in range(len(years_ls))]
    year_colors = ["rgb" + str(mpl_cmap("viridis")(x)[:3]) for x in cmap_ls]

    # create year-agnostic date column for plotting all years against one another
    def dt_replace_year(dt_series, set_year):
        df = pd.DataFrame()
        df["year"] = [set_year]*len(dt_series)
        df["month"] = dt_series.dt.month
        df["day"] = dt_series.dt.day
        return pd.to_datetime(df)

    dummy_year = 2000
    sleep_descr_df["Prev_Mon_Day"] = dt_replace_year(sleep_descr_df["Prev_Day"], dummy_year)
    sleep_event_df["Prev_Mon_Day"] = dt_replace_year(sleep_event_df["Prev_Day"], dummy_year)
    
    # interpret click values for updating UI & data filters
    [wn_color, offn_color, tod_filter] = react_tod_clicks(wn_clicks, offn_clicks)
    [mon_color, tue_color, wed_color, thu_color, fri_color, sat_color, sun_color, dow_filter] = \
        react_dow_clicks(mon_clicks, tue_clicks, wed_clicks, thu_clicks, fri_clicks, sat_clicks, sun_clicks)

    # filter data by getting sleep session IDs which meet filter criteria
    sleep_descr_df = sleep_descr_df[(sleep_descr_df["Day"].isin(dow_filter)) & 
                        (sleep_descr_df["Is_Workday"].isin(tod_filter))]
    sleep_event_df = sleep_event_df[sleep_event_df["Sleep_Session_ID"]. \
                isin(sleep_descr_df["Sleep_Session_ID"])]

    # set variable dependent on the selected plot picker option
    data_df = pd.DataFrame()
    if plot_picker == "fell asleep":
        data_df["x"] = sleep_event_df.query('Event == "Fell Asleep"').Prev_Mon_Day
        data_df["y"] = sleep_event_df.query('Event == "Fell Asleep"').ToD
        data_df["year"] = sleep_event_df.query('Event == "Fell Asleep"').Prev_Day.dt.year
        y_title_plot = "Fell Asleep Time"
        y_range_plot = [0, 4]
        y_tick_labels = ["1 AM", "3 AM"]
        y_tick_vals = [1, 3]
    elif plot_picker == "woke up":
        data_df["x"] = sleep_event_df.query('Event == "Woke Up"').Prev_Mon_Day
        data_df["y"] = sleep_event_df.query('Event == "Woke Up"').ToD
        data_df["year"] = sleep_event_df.query('Event == "Woke Up"').Prev_Day.dt.year
        y_title_plot = "Woke Up Time"
        y_range_plot = [7, 11]
        y_tick_labels = ["8 AM", "10 AM"]
        y_tick_vals = [8, 10]
    elif plot_picker == "dur":
        data_df["x"] = sleep_descr_df.Prev_Mon_Day
        data_df["y"] = sleep_descr_df.Total_Dur.dt.seconds/(60.*60)
        data_df["year"] = sleep_descr_df.Year
        y_title_plot = "Duration (hours)"
        y_range_plot = [5, 10]
        y_tick_labels = None
        y_tick_vals = None

    # make 2 subplots: top plot will show sleep data, bottom plot will show sunrise or sunset
    fig = subplots.make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], \
                                 column_widths=[1], vertical_spacing=0.06)

    # scatter plot for each year
    for i, year in enumerate(years_ls):
        # isolate data for [year]
        data_year_df = data_df[data_df["year"] == year]

        fig.add_trace(go.Scatter(
            name=str(year),
            x=data_year_df.x,
            y=data_year_df.y,
            hoverinfo="skip",
            marker_color=year_colors[i],
            marker_line_width=0, 
            marker_size=6,
            mode="markers",
            opacity=0.3,
            showlegend=False
        ), row=1, col=1)
    
    # plot a fitted-curve to each year
    for i, year in enumerate(years_ls):
        # isolate data for [year]
        data_year_df = data_df[data_df["year"] == year]

        # add smooth signal line for waking up
        x_numeric = data_year_df.x - dt.datetime(dummy_year, 1, 1)
        y_numeric = data_year_df.y
        fit_series = lowess(y_numeric, x_numeric.dt.days, is_sorted=True, frac=0.2, it=0)

        # define hoverinfo depending on variable being plotted
        if plot_picker == "dur":
            fit_series_dt = dt.datetime(dummy_year, 1, 1) + \
                           pd.to_timedelta(fit_series[:,0], unit="days")
            hover_info = fit_series_dt.strftime("%B %d")
            hover_tmp = "%{text}<br>%{y:.2f} hours"
        else:
            fit_series_dt = dt.datetime(dummy_year, 1, 1) + \
                           pd.to_timedelta(fit_series[:,0], unit="days") + \
                           pd.to_timedelta(fit_series[:,1], unit="hours")
            hover_info = fit_series_dt.strftime("%B %d, %r")
            hover_tmp = "%{text}"
        
        fig.add_trace(go.Scatter(
            name=str(year),
            x=dt.datetime(dummy_year, 1, 1) + pd.to_timedelta(fit_series[:,0] - 1, unit="D"),
            y=fit_series[:,1],
            text=hover_info,
            hovertemplate=hover_tmp,
            mode="lines",
            line=dict(
                color=year_colors[i],
                width=4
            ),
            opacity=1,
            showlegend=False
        ), row=1, col=1)

        # add dummy trace to make bigger markers in the legend
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                            marker=dict(size=8, color=year_colors[i]),
                            showlegend=True, name=str(year)))
    
    # provide bottom reference plot to sunset
    # first, sunset and sunrise will be averaged for each day of year
    sun_df["Mon_Day"] = dt_replace_year(sun_df["Date"], dummy_year)
    sun_agg_df = pd.DataFrame()
    sun_agg_df["Date"] = pd.to_datetime(sun_df["Mon_Day"].unique()).sort_values()
    sun_agg_fields = ["Sunrise_ToD", "Sunset_ToD"]
    for sun_agg_field in sun_agg_fields:
        sun_agg = sun_df.groupby("Mon_Day")[sun_agg_field].mean()
        sun_agg_df = sun_agg_df.merge(sun_agg, left_on="Date", right_on="Mon_Day")
    sun_agg_df["Sunrise"] = pd.to_datetime(sun_agg_df.Date) + \
                          pd.to_timedelta(sun_agg_df["Sunrise_ToD"], unit="hour")
    sun_agg_df["Sunset"] = pd.to_datetime(sun_agg_df.Date) + \
                          pd.to_timedelta(sun_agg_df["Sunset_ToD"] + 24, unit="hour")

    # now set y axis properties and make bottom reference plot
    if plot_picker == "woke up":
        y_title_sun = "Sunrise Time"
        y_range_sun = [5, 10]
        y_tick_labels_sun = ["6 AM", "8 AM"]
        y_tick_vals_sun = [6, 8]

        fig.add_trace(go.Scatter(
            name="Sunrise",
            x=sun_agg_df["Date"],
            y=sun_agg_df["Sunrise_ToD"],
            text=sun_agg_df.Sunrise.dt.strftime("%B %d, %r"),
            hovertemplate="%{text}",
            fillcolor=invis,
            fill="tozeroy",
            mode="lines",
            marker_color=invis,
            marker_line_width=0,
            marker_size=0,
            line_color=invis,
            opacity=0,
            showlegend=False
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            name="Above Sunrise",
            x=sun_agg_df["Date"],
            y=[16]*len(sun_agg_df),
            text=sun_agg_df.Sunrise.dt.strftime("%B %d, %r"),
            hovertemplate="%{text}",
            fill="tonextx",
            fillcolor=sun_fill_color,
            mode="lines",
            marker_color=sun_fill_color,
            marker_line_width=0,
            marker_size=0,
            line_color=sun_fill_color,
            opacity=1,
            showlegend=False
        ), row=2, col=1)
    
    else:
        y_title_sun = "Sunset Time"
        y_range_sun = [-7, -1]
        y_tick_labels_sun = ["6 PM", "9 PM"]
        y_tick_vals_sun = [-6, -3]

        fig.add_trace(go.Scatter(
            name="Below Sunset",
            x=sun_agg_df["Date"],
            y=[-17]*len(sun_agg_df),
            text=sun_agg_df.Sunset.dt.strftime("%B %d, %r"),
            hovertemplate="%{text}",
            fillcolor=invis,
            fill="tonextx",
            mode="lines",
            marker_color=invis,
            marker_line_width=0,
            marker_size=0,
            line_color=invis,
            opacity=0,
            showlegend=False
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            name="Sunset",
            x=sun_agg_df["Date"],
            y=sun_agg_df["Sunset_ToD"],
            text=sun_agg_df.Sunset.dt.strftime("%B %d, %r"),
            hovertemplate="%{text}",
            fillcolor=sun_fill_color,
            fill="tonextx",
            mode="lines",
            marker_color=sun_fill_color,
            marker_line_width=0,
            marker_size=0,
            line_color=sun_fill_color,
            opacity=1,
            showlegend=False
        ), row=2, col=1)

    # add dummy trace to make bigger markers in the legend
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                        marker=dict(size=8, color=sun_fill_color),
                        showlegend=True, name='Sun is Up'))
    
    # define all x-axes
    fig.update_xaxes(row=1, col=1, zeroline=True, #dtick="M12", 
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        range=[dt.date(dummy_year, 1, 1), dt.date(dummy_year, 12, 31)], showticklabels=True,
        tickformat="%b")
    
    fig.update_xaxes(row=2, col=1, zeroline=True, #dtick="M12", 
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        range=[dt.date(dummy_year, 1, 1), dt.date(dummy_year, 12, 31)], showticklabels=False,
        tickformat="%b")
    
    # define all y-axes
    fig.update_yaxes(row=1, col=1, zeroline=True, zerolinecolor="gray", zerolinewidth=0.5,
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        ticktext=y_tick_labels, tickvals=y_tick_vals, range=y_range_plot,
        title_text=y_title_plot)

    fig.update_yaxes(row=2, col=1, zeroline=True, zerolinecolor="gray", zerolinewidth=0.5,
        linecolor="gray", linewidth=0.5, gridcolor="gray", gridwidth=0.5, mirror=True,
        ticktext=y_tick_labels_sun, tickvals=y_tick_vals_sun, range=y_range_sun,
        title_text=y_title_sun)
    
    # define overall layout and legend properties
    fig.update_layout(
        paper_bgcolor=invis,
        plot_bgcolor=invis,
        margin=go.layout.Margin(l=50, r=20, b=10, t=10),
        #width=1200,
        height=450,
        autosize=True,
        legend=go.layout.Legend(
            x=0,
            y=1.1,
            traceorder="normal",
            font=dict(
                family="sans-serif",
                size=12,
                color="black"
            ),
            bgcolor="white",
            bordercolor="gray",
            borderwidth=0.5),
        legend_orientation="h")
    
    return [fig, mon_color, tue_color, wed_color, thu_color, \
            fri_color, sat_color, sun_color, wn_color, offn_color]

if __name__ == '__main__':
    app.run_server(debug=True)