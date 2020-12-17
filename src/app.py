from flask import Flask, request, Blueprint
from flask import jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import execute_values
import logging
import os, sys
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

VERSION = "v1_beta"

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

@bp.route('/', methods=["GET"])
def index():
    return {
            "success" : {
                "v" : VERSION,
                "descriptions" : "API for reserving or registering ASKE-IDs",
                "routes": {
                    f"/api/{VERSION}/reserve" : "Reserve a block of ASKE-IDs for later registration.",
                    f"/api/{VERSION}/register" : "Register a location for a reserved ASKE-ID."
                    }
                }
        }

@bp.route('/reserve', methods=["GET", "POST"])
def reserve():
    helptext = {
            "v" : VERSION,
            "description": "Reserve a block of ASKE-IDs for later registration.",
            "options" : {
                "parameters" : {
                    "api_key" : "(required) API key assigned to an ASKE-ID registrant. Can also be passed as a header in the 'x-api-key' field."
                    "n" : "(option, int, default 10) Number of ASKE-IDs to reserve."
                    },
                "methods" : ["POST"],
                "accepted_body" : "{objects: [ASKE-ID, location]}",
                "output_formats" : ["json"],
                "fields" : {
                    "reserved_ids" : "List of unique ASKE-IDs reserved for usage by the associated registrant API key."
                    },
                "examples": []
                }
            }

    if request.method == "GET":
        return {"success" : helptext}

    headers = request.headers
    api_key = headers.get('x-api-key', default = None)
    if api_key is None:
        api_key = request.args.get('api_key', default=None)
    if api_key is None:
        return {"error" :
                {
                    "message" : "You must specify an API key!",
                    "v" : VERSION,
                    "about" : helptext
                }
                }

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

@bp.route('/register', methods=["POST"])
def register():
    helptext = {
            "v" : VERSION,
            "description": "Register a location for a reserved ASKE-ID.",
            "options" : {
                "parameters" : {
                    "api_key" : "(required) API key assigned to an ASKE-ID registrant. Can also be passed as a header in the 'x-api-key' field."
                    },
                "body" : "POSTed request body must be a JSON object of the form [[ASKE-ID, location], [ASKE-ID, location]].",
                "methods" : ["POST"],
                "output_formats" : ["json"],
                "fields" : {
                    "registered_ids" : "List of successfully registered (or updated) ASKE-IDs."
                    },
                "examples": []
                }
            }
    if request.method == "GET":
        return {"success" : helptext}

    headers = request.headers
    api_key = headers.get('x-api-key', default = None)
    if api_key is None:
        api_key = request.args.get('api_key', default=None)
        logging.info(f"got api_key from request.args")
    if api_key is None:
        return {"error" :
                {
                    "message" : "You must specify an API key!",
                    "v" : VERSION,
                    "about" : helptext
                }
                }
    try:
        objects = request.get_json()
    except:
        return {"error" :
                {
                    "message" : "Invalid body! Registration expects a JSON object of the form [[<ASKE-ID>, <location>], [<ASKE-ID>, <location>]].",
                    "v" : VERSION,
                    "about" : helptext
                }
                }

    registered = []
    for oid, location in objects:
        logging.info(f"Registering {oid} to {location}")
        # TODO: maybe get all oids this key can register and do the check in-memory instead of against the DB?
        try:
            cur.execute("SELECT r.id FROM registrant r, object o WHERE o.registrant_id=r.id AND r.api_key=%(api_key)s AND o.id=%(oid)s", {"api_key" : api_key, "oid" : oid})
            registrant_id = cur.fetchone()
            if registrant_id is None:
                continue
    #            return {"error" : "Provided API key not allowed to register this ASKE-ID!"}
            cur.execute("UPDATE object SET location=%(location)s WHERE id=%(oid)s", {"location" : location, "oid": oid})
            conn.commit()
            registered.append(oid)
        except:
            logging.info(f"Couldn't register {oid} to {location}.")
            conn.commit()
    return {"success" : {
            "registered_ids" : registered
        }
        }

@bp.route('/id/<oid>', methods=["GET"])
        cur.execute("SELECT o.id, o.location, r.name FROM registrant r, object o WHERE o.id=%(oid)s", {"oid" : oid})
        oid, location, registrant = cur.fetchone()
        if registrant_id is None:
            return {"error" : "ASKE-ID not found!"}
        else:
            return {"success" : {
                "identifier" : [{"type" : "_aske-id", "id" : oid}],
                "link" : [{"url" : location}],
                "registrant" : registrant
                }
            }

if 'PREFIX' in os.environ:
    logging.info(f"Stripping {os.environ['PREFIX']}")
    app.register_blueprint(bp, url_prefix=os.environ['PREFIX'])
else:
    logging.info("No prefix stripped.")
    app.register_blueprint(bp)
CORS(app)

#if __name__ == '__main__':
#    app.run(debug=True,host='0.0.0.0', port=80)
