# College Event Management System

A Flask and MySQL application for publishing college events, managing registrations, and administering event listings.

## Requirements

- Python 3.10 or newer
- MySQL Server

## Setup

1. Clone the repository and open its folder.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a MySQL database and tables by running `schema.sql` in MySQL.
5. Copy `.env.example` to `.env` and set your database credentials and a unique `SECRET_KEY`.
6. Create the first administrator:

   ```bash
   python create_admin.py
   ```

7. Start the application:

   ```bash
   python app.py
   ```

The app creates `Static/uploads` as needed for event images. Uploaded images and local environment settings are excluded from Git.
