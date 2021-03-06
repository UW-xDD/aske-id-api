from flask import Flask, request, Blueprint
from flask import jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import execute_values
import logging
import os, sys
import time
from uuid import uuid4, UUID
logging.basicConfig(format='%(levelname)s :: %(asctime)s :: %(message)s', level=logging.DEBUG)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.url_map.strict_slashes = False
bp = Blueprint('ASKE-ID-api', __name__)

def prepare(objects):
    for obj in objects:
        if len(obj) == 3:
            yield(obj)
        else: # no description
            yield((obj[0], obj[1], ''))

def table_exists(cur, table_name):
    """
    Check if a table exists in the current database

    :cur: psql cursort
    :table_name: Name of table to search for.
    :returns: True if it exists, False if not

    """
    cur.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' """)
    for table in cur.fetchall():
        logging.info(table[0])
        if table_name == table[0]:
            return True
        else:
            continue
    return False

if "PG_HOST" in os.environ:
    host = os.environ["PG_HOST"]
else:
    host = 'aske-id-registration'

if "PG_USER" in os.environ:
    user = os.environ["PG_USER"]
else:
    user = 'zalando'

VERSION = "v1_beta"


cconn = psycopg2.connect(host=host, user=user, password=os.environ["PG_PASSWORD"], database='aske_id')
cconn.autocommit = True
ccur = cconn.cursor()

if not table_exists(ccur, "registrant"):
    ccur.execute("""
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        """)
    cconn.commit()
    ccur.execute("""
        CREATE TABLE registrant (
            id SERIAL PRIMARY KEY,
            registrant text,
            api_key uuid DEFAULT uuid_generate_v4()
        );""")
    cconn.commit()
if not table_exists(ccur, "object"):
    ccur.execute("""
        CREATE TABLE object (
            id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
            registrant_id integer REFERENCES registrant(id),
            location text DEFAULT NULL,
            description text
        );""")
    cconn.commit()
ccur.close()
cconn.close()

@bp.route('/', methods=["GET"])
def index():
    return {
            "success" : {
                "v" : VERSION,
                "descriptions" : "API for reserving or registering ASKE-IDs",
                "routes": {
                    f"/reserve" : "Reserve a block of ASKE-IDs for later registration.",
                    f"/register" : "Register a location for a reserved ASKE-ID.",
                    f"/create" : "Create and ASKE-ID for existing resources.",
                    f"/id" : "Lookup an ASKE-ID."
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
                    "api_key" : "(required) API key assigned to an ASKE-ID registrant. Can also be passed as a header in the 'x-api-key' field.",
                    "n" : "(option, int, default 10) Number of ASKE-IDs to reserve."
                    },
                "methods" : ["POST"],
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
    try:
        check = UUID(api_key)
    except ValueError:
        check = False

    if api_key is None or check is False:
        return {"error" :
                {
                    "message" : "You must specify a valid API key!",
                    "v" : VERSION,
                    "about" : helptext
                }
                }

    n_requested = request.args.get('n', default=10)
    if not isinstance(n_requested, int):
        n_requested = int(n_requested)

    conn = psycopg2.connect(host=host, user=user, password=os.environ["PG_PASSWORD"], database='aske_id')
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT id FROM registrant WHERE api_key=%(api_key)s", {"api_key" : api_key})
    registrant_id = cur.fetchone()
    if registrant_id is None:
        cur.close()
        conn.close()
        return {"error" :
                {"message" : "Provided API key not allowed to reserve ASKE-IDs!",
                    "v": VERSION,
                    "about" : helptext
                    }
                }

    uuids = [str(uuid4()) for i in range(n_requested)]

    # TODO : catch foreign key exception
    execute_values(cur,
        "INSERT INTO object (id, registrant_id) VALUES %s",
        [(uuid, registrant_id) for uuid in uuids])
    conn.commit()
    cur.close()
    conn.close()
    return {"success" : True, "reserved_ids" : uuids}

@bp.route('/create', methods=["POST", "GET"])
def create():
    helptext = {
            "v" : VERSION,
            "description": "Create and register a new ASKE-ID.",
            "options" : {
                "parameters" : {
                    "api_key" : "(required) API key assigned to an ASKE-ID registrant. Can also be passed as a header in the 'x-api-key' field."
                    },
                "body" : "POSTed request body must be a JSON object of the form [location1, location2].",
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
                    "message" : "Invalid body! Registration expects a JSON object of the form [<location>, <location>] or [[<location>, <description>], [<location>, <description>], ...].",
                    "v" : VERSION,
                    "about" : helptext
                }
                }

    conn = psycopg2.connect(host=host, user=user, password=os.environ["PG_PASSWORD"], database='aske_id')
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT id FROM registrant WHERE api_key=%(api_key)s", {"api_key" : api_key})
    check = cur.fetchone()
    if check is None:
        cur.close()
        conn.close()
        return {"error" :
                {
                    "message" : "Invalid API key!",
                    "v" : VERSION,
                    "about" : helptext
                }
                }

    registered = []
    if isinstance(objects[0], list):
        for location, description in objects:
            try:
                cur.execute("INSERT INTO object (location, description, registrant_id) VALUES (%(location)s, %(description)s, %(registrant_id)s) RETURNING id, location, description", {"location" : location, "description" : description, "registrant_id" : check})
                oid, location, description = cur.fetchone()
                conn.commit()
                registered.append((oid, location, description))
            except:
                logging.info(f"Couldn't register {location}.")
                logging.info(sys.exc_info())
                conn.commit()
    else:
        for location in objects:
            try:
                cur.execute("INSERT INTO object (location, registrant_id) VALUES (%(location)s, %(registrant_id)s) RETURNING id, location", {"location" : location, "registrant_id" : check})
                oid, location = cur.fetchone()
                conn.commit()
                registered.append((oid, location))
            except:
                logging.info(f"Couldn't register {location}.")
                logging.info(sys.exc_info())
                conn.commit()
    cur.close()
    conn.close()
    return {"success" : {
            "registered_ids" : registered
        }
        }

@bp.route('/register', methods=["POST", "GET"])
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

    try:
        check = UUID(api_key)
    except ValueError:
        check = False

    if api_key is None or check is False:
        return {"error" :
                {
                    "message" : "You must specify a valid API key!",
                    "v" : VERSION,
                    "about" : helptext
                }
                }
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
    conn = psycopg2.connect(host=host, user=user, password=os.environ["PG_PASSWORD"], database='aske_id')
    conn.autocommit = True
    cur = conn.cursor()
    for oid, location, description in prepare(objects):
        logging.info(f"Registering {oid} to {location}")
        # TODO: maybe get all oids this key can register and do the check in-memory instead of against the DB?
        try:
            cur.execute("SELECT r.id FROM registrant r, object o WHERE o.registrant_id=r.id AND r.api_key=%(api_key)s AND o.id=%(oid)s", {"api_key" : api_key, "oid" : oid})
            registrant_id = cur.fetchone()
            if registrant_id is None:
                continue
    #            return {"error" : "Provided API key not allowed to register this ASKE-ID!"}
            cur.execute("UPDATE object SET location=%(location)s, description=%(description)s WHERE id=%(oid)s", {"location" : location, "description" : description, "oid": oid})
            conn.commit()
            registered.append(oid)
        except:
            logging.info(f"Couldn't register {oid} to {location}.")
            conn.commit()
    cur.close()
    conn.close()
    return {"success" : {
            "registered_ids" : registered
        }
        }

@bp.route('/id/', defaults={'oid': None})
@bp.route('/id', defaults={'oid': None})
@bp.route('/id/<oid>', methods=["GET"])
def lookup(oid):
    helptext = {
            "v" : VERSION,
            "description": "Look up an ASKE-ID ",
            "options" : {
                "parameters" : {
                    "aske_id" : "ASKE-ID to look up (may also be supplied as a bare positional argument on this URL)."
                    },
                "output_formats" : ["bibjson"],
                "examples": ['/id/5ed07aa7-b7e2-4ee7-bd8c-dde5c47a1d8e', '/id?aske_id=5ed07aa7-b7e2-4ee7-bd8c-dde5c47a1d8e', '/id?all']
                }
            }

    if oid is None:
        oid = request.args.get('aske_id', default=None)
    if "all" in request.args:
        oid = 'all'
    if oid is None:
        return{
                "error" : {
                    "message": "You must provide an ASKE-ID to look up!",
                    "v": VERSION,
                    "about" : helptext
                    }
                }
    conn = psycopg2.connect(host=host, user=user, password=os.environ["PG_PASSWORD"], database='aske_id')
    conn.autocommit = True
    cur = conn.cursor()
    results = []
    if oid=='all':
        cur.execute("SELECT o.id, o.location, o.description, r.registrant FROM registrant r, object o WHERE o.registrant_id=r.id AND location IS NOT NULL", {"oid" : oid})
        for oid, location, description, registrant in cur.fetchall():
            results.append(
                    {
                        "identifier" : [{"type" : "_aske-id", "id" : oid}],
                        "link" : [{"url" : location}],
                        "metadata" : {"description" : description},
                        "registrant" : registrant
                        }
                    )
    else:
        try:
            cur.execute("SELECT o.id, o.location, o.description, r.registrant FROM registrant r, object o WHERE o.id=%(oid)s AND o.registrant_id=r.id", {"oid" : oid})
            oid, location, description, registrant = cur.fetchone()
            results.append(
                    {
                        "identifier" : [{"type" : "_aske-id", "id" : oid}],
                        "link" : [{"url" : location}],
                        "metadata" : {"description" : description},
                        "registrant" : registrant
                        }
                    )
        except (TypeError, psycopg2.errors.InvalidTextRepresentation):
            cur.close()
            conn.close()
            return{
                    "error" : {
                        "message": "ASKE-ID not found!",
                        "v": VERSION,
                        "about" : helptext
                        }
                    }
    cur.close()
    conn.close()
    return {"success" :{
            "objects" : results
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
