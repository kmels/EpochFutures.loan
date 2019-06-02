from flask import Blueprint
app = Blueprint('errors', __name__)

from endpoints import ForbiddenAccess

@app.errorhandler(ForbiddenAccess)
def handle_forbidden(error):
    from flask import jsonify
    response = jsonify({"message": error.message, "endpoint": error.endpoint})
    response.status_code = 403
    return response

