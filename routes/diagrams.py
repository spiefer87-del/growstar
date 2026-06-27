from flask import send_file, request


def register(app):

    @app.route("/api/diagrams/export")
    def export_diagrams():
        return send_file(
            "data.db",
            as_attachment=True,
            download_name="grow_diagrams.db"
        )

    @app.route("/api/diagrams/import", methods=["POST"])
    def import_diagrams():
        with open("data.db", "wb") as f:
            f.write(request.data)

        return {
            "status": "ok"
        }
