from flask import jsonify

def api_response(success: bool, data=None, error=None, status_code=200):
    """
    Standard API Response JSON Wrapper.
    """
    return jsonify({
        "success": success,
        "data": data,
        "error": error
    }), status_code
