from flask import Flask, request, abort, Blueprint
from flask import jsonify
from flask_cors import CORS
import psycopg2
import logging
import glob
import os
import json
import base64
from collections import OrderedDict
logging.basicConfig(format='%(levelname)s :: %(asctime)s :: %(message)s', level=logging.DEBUG)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.url_map.strict_slashes = False
bp = Blueprint('ASKE-ID-api', __name__)

def table_exists(cur, table_name):
    """
    Check if a table exists in the current database

    :cur: psql cursort
    :table_name: Name of table to search for.
    :returns: True if it exists, False if not

    """
    cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' """)
    for table in cur.fetchall():
        if table_name == table[0]:
            return True
        else:
            continue
    return False

conn = psycopg2.
conn = psycopg2.connect(host='aske-id-registration', user='zalando', password=os.environ["PG_PASSWORD"], sslmode='require', database='aske_id')
cur = conn.cursor()

if not table_exists(cur, "registrant"):
    cur.execute("""
        CREATE TABLE registrant (
            id SERIAL PRIMARY KEY,
            registrant text,
            api_key uuid DEFAULT public.uuid_generate_v4(),
        );""")
    conn.commit()
if not table_exists(cur, "object"):
    cur.execute("""
        CREATE TABLE object (
            id uuid PRIMARY KEY DEFAULT public.uuid_generate_v4(),
            registrant_id integer REFERENCES registrant(id),
            location text DEFAULT NULL
        );""")
    conn.commit()

@bp.route('/', defaults={'set_name': None})
@bp.route('/<set_name>')
@bp.route('/<set_name>/')
def get_set(set_name):
    logging.info(f"requested {request.endpoint}")
    logging.info(set_name)

    if set_name is None:
        results_obj = {
                "description" : "Sets are a (still in development) construct within xDD creating a way for users to define, search, and interact with a set of documents within the xDD corpus. These sets may be defined by topic, keywords, journals, or simply a list of DOIs. Browse to any of the sets listed below (e.g. /sets/xdd-covid-19) for the set definitions along with available products created from each.",
                "available_sets" : list(sets.keys())
                }
        return jsonify(results_obj)
    else :
        set_name = set_name.lower()
        if set_name not in sets:
            return {"error" : "Set undefined!"}
        return jsonify(sets[set_name])

if 'PREFIX' in os.environ:
    logging.info(f"Stripping {os.environ['PREFIX']}")
    app.register_blueprint(bp, url_prefix=os.environ['PREFIX'])
else:
    logging.info("No prefix stripped.")
    app.register_blueprint(bp)
CORS(app)

#if __name__ == '__main__':
#    app.run(debug=True,host='0.0.0.0', port=80)
