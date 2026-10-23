CREATE DATABASE IF NOT EXISTS college_events;
USE college_events;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'admin'
);

CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(160) NOT NULL,
    description TEXT,
    category VARCHAR(80),
    venue VARCHAR(160),
    event_date DATETIME NOT NULL,
    capacity INT NULL,
    status ENUM('Draft', 'Published', 'Completed', 'Cancelled')
        NOT NULL DEFAULT 'Draft'
);

CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_no VARCHAR(40) NOT NULL UNIQUE,
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(190) NOT NULL,
    department VARCHAR(120) NOT NULL
);

CREATE TABLE registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    event_id INT NOT NULL,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_student_event (student_id, event_id),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);