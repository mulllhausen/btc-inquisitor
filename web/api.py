#!/usr/bin/env python2.7
"""
this is the btc-inquisitor api controller. all endpoints return json. for
browser security only HTTP POST is supported.
"""

import web
import json

urls = (
    "/", "index",
    "/getbalancehistory", "getbalancehistory",
)

class index:
    def POST(self):
        data = {
            "Data": {
                "Items": ["getbalancehistory"],
                "Meta": {
                    "Title": "list api functionality (endpoints)"
                }
            },
            "Error": {
                "Code": 0,
                "Status": ""
            },
            "Endpoint": web.ctx.path
        }
        return json.dumps(data)

class getbalancehistory:
    def POST(self, address):
        return "balance for address %s" % address

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()
