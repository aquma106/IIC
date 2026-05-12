if not file or not file.filename:
            return jsonify({"success": False, "message": "No image uploaded"}), 400

        filename = file.filename
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        execute_query(
            "INSERT INTO gallery (title, image) VALUES (%s, %s)",
            (title, filename)
        )