from app import create_app

app = create_app() ## membuat app

if __name__ == '__main__':
    # Jalankan server di port 5000 dengan mode debug aktif
    app.run(debug=True, port=5000)