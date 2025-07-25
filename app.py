from flask import Flask, render_template
from sleeper_data_pypline.mongo import connect
from sleeper_data_pypline.queries import get_highest_bids_of_all_time

app = Flask(__name__)

@app.route('/')
def index():
    MongoClient = connect()
    bids = get_highest_bids_of_all_time(10)
    return render_template('index.html', bids=bids)

if __name__ == '__main__':
    app.run(debug=True)
