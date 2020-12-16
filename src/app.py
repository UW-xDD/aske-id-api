from flask import Flask, request, Blueprint
from flask import jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import execute_values
import logging
import os
from uuid import uuid4
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

conn = psycopg2.connect(host='aske-id-registration', user='zalando', password=os.environ["PG_PASSWORD"], sslmode='require', database='aske_id')
cur = conn.cursor()

if not table_exists(cur, "registrant"):
    cur.execute("""
        CREATE TABLE registrant (
            id SERIAL PRIMARY KEY,
            registrant text,
            api_key uuid DEFAULT uuid_generate_v4()
        );""")
    conn.commit()
if not table_exists(cur, "object"):
    cur.execute("""
        CREATE TABLE object (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            registrant_id integer REFERENCES registrant(id),
            location text DEFAULT NULL
        );""")
    conn.commit()

@bp.route('/reserve')
def reserve():
    api_key = request.args.get('api_key', default=None)
    if api_key is None:
        return {"error" : "You must specify an API key!"}

    n_requested = request.args.get('n', default=10)

    cur.execute("SELECT id FROM registrant WHERE api_key=%(api_key)s", {"api_key" : api_key})
    registrant_id = cur.fetchone()
    if registrant_id is None:
        return {"error" : "Provided API key not allowed to reserve ASKE-IDs!"}

    uuids = [str(uuid4()) for i in range(n_requested)]

    # TODO : catch foreign key exception
    execute_values(cur,
        "INSERT INTO object (id, registrant_id) VALUES %s",
        [(uuid, registrant_id) for uuid in uuids])
    conn.commit()
    return {"success" : True, "reserved_ids" : uuids}

@bp.route('/register/<oid>')
def register(oid):
    api_key = request.args.get('api_key', default=None)
    if api_key is None:
        return {"error" : "You must specify an API key!"}

    location = request.args.get('location')
    if location is None:
        return {"error" : "You must specify a location to register this ASKE-id."}

    #  check that this API key is allowed to register this oid
    cur.execute("SELECT r.id FROM registrant r, object o WHERE o.registrant_id=r.id AND r.api_key=%(api_key)s AND o.id=%(oid)s", {"api_key" : api_key, "oid" : oid})
    registrant_id = cur.fetchone()
    if registrant_id is None:
        return {"error" : "Provided API key not allowed to register this ASKE-ID!"}
    cur.execute("UPDATE object SET location=%(location)s WHERE o.id=%(oid)s", {"location" : location, "oid": oid})
    conn.commit()
    return {"success" : True}

if 'PREFIX' in os.environ:
    logging.info(f"Stripping {os.environ['PREFIX']}")
    app.register_blueprint(bp, url_prefix=os.environ['PREFIX'])
else:
    logging.info("No prefix stripped.")
    app.register_blueprint(bp)
CORS(app)

#if __name__ == '__main__':
#    app.run(debug=True,host='0.0.0.0', port=80)
