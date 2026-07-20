-- Extend questions table with presentation_style and multilevel hints
ALTER TABLE questions
ADD COLUMN presentation_style VARCHAR(30) NOT NULL DEFAULT 'text_based',
ADD COLUMN hint_level2_ms TEXT NOT NULL DEFAULT '',
ADD COLUMN hint_level3_ms TEXT NOT NULL DEFAULT '';

-- Create comprehensive_practice_sessions table
CREATE TABLE comprehensive_practice_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    current_question_number INT NOT NULL DEFAULT 0,
    phase VARCHAR(20) NOT NULL DEFAULT 'diagnosis',
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    weak_subtopics_json TEXT NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    INDEX idx_student_session (student_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create style_preferences table
CREATE TABLE style_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    presentation_style VARCHAR(30) NOT NULL,
    total_attempts INT NOT NULL DEFAULT 0,
    correct_count INT NOT NULL DEFAULT 0,
    total_time_seconds INT NOT NULL DEFAULT 0,
    accuracy FLOAT NOT NULL DEFAULT 0.0,
    avg_time_seconds FLOAT NOT NULL DEFAULT 0.0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id),
    UNIQUE KEY unique_student_style (student_id, presentation_style)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
