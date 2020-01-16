# sleepwithdash
A plotly|Dash app which visualizes sleep data from my smartwatches

# Deploy to Heroku
In order to deploy this app to Heroku, three build packs must be added to the Heroku app:
1. heroku/python
2. https://github.com/heroku/heroku-buildpack-google-chrome.git
3. https://github.com/heroku/heroku-buildpack-chromedriver.git

# Deploy to local Windows machine
This app can also run a local Windows machine, but the `project_path` variable needs to changed to wherever the repository is saved.  The virtual environment should be built with conda and the `conda_requirements.txt` file by `conda create --name myenv --file conda_requirements.txt`.  Executing the script `app.py` will then launch the host process for the app to be viewed in an internet browser.

Further discussion of this app's development can be found at https://buckeye17.github.io/Sleep-Dashboard/
