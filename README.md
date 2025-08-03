# 🎓 Student Results Portal

A modern, secure web application for viewing student academic results with real-time grade modification tracking. Built with FastAPI and featuring a responsive design with automatic dark mode support.

## ✨ Features

### 🔐 Authentication & Security

- **Student Authentication**: Secure login using registration number and date of birth
- **Session Management**: Persistent authentication sessions
- **Access Control**: Students can only access their own results
- **Data Privacy**: All student data is protected and isolated

### 📊 Results Management

- **PDF Integration**: Direct viewing of original result PDFs
- **Real-time Grade Changes**: Students can modify grades with instant feedback
- **Grade Change Tracking**: Complete audit trail of all grade modifications
- **GPA Recalculation**: Automatic GPA updates based on grade changes
- **Bulk Download**: Download all semester results as a ZIP file

### 🎨 Modern UI/UX

- **Dark Mode**: Automatic dark/light theme based on system preference
- **Mobile Responsive**: Optimized for all device sizes
- **Glass Morphism Design**: Modern, elegant interface
- **Interactive Elements**: Smooth animations and transitions
- **Notification System**: Real-time feedback for user actions

### 👨‍💼 Administrative Features

- **Admin Dashboard**: Monitor all grade changes across students
- **API Endpoints**: RESTful APIs for data access
- **Change Analytics**: Track patterns in grade modifications
- **Export Capabilities**: Data export for reporting

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL database (Supabase recommended)
- Supabase Storage for PDF files

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd student-results-portal
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Setup**

   Create a `.env` file in the project root:

   ```env
   # Database Configuration
   DATABASE_URL=postgresql://username:password@localhost:5432/database_name
   # OR use Supabase (recommended)
   SUPABASE_PROJECT_ID=your_project_id
   DB_PASSWORD=your_db_password
   SUPABASE_PORT=5432

   # Supabase Storage
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your_service_key
   STORAGE_BUCKET_NAME=your_bucket_name
   ```

4. **Database Setup**

   ```bash
   # Initialize the database
   python database.py

   # Run grade changes migration
   python add_grade_changes_table.py
   ```

5. **Start the server**

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Access the application**

   Open your browser and navigate to `http://localhost:8000`

## 📋 Project Structure

```
student-results-portal/
├── 📁 static/
│   └── style.css                 # CSS styles with dark mode support
├── 📁 templates/
│   ├── index.html               # Student search page
│   ├── auth.html                # Authentication page
│   ├── student.html             # Student results page
│   ├── admin_grade_changes.html # Admin dashboard
│   └── 404.html                 # Error page
├── 📁 logs/                     # Application logs
├── 📁 __pycache__/             # Python cache files
├── main.py                      # FastAPI application entry point
├── database.py                  # Database models and configuration
├── add_grade_changes_table.py   # Database migration script
├── requirements.txt             # Python dependencies
├── render.yaml                  # Render deployment configuration
├── students.json               # Sample student data
├── subjects.json               # Sample subject data
└── README.md                   # Project documentation
```

## 🗄️ Database Schema

### Students Table

```sql
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    regno VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    dob VARCHAR(10) NOT NULL
);
```

### Subjects Table

```sql
CREATE TABLE subjects (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    credits INTEGER NOT NULL
);
```

### Semesters Table

```sql
CREATE TABLE semesters (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    semester INTEGER NOT NULL,
    gpa DECIMAL(4,2)
);
```

### Grades Table

```sql
CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    semester_id INTEGER REFERENCES semesters(id),
    subject_id INTEGER REFERENCES subjects(id),
    grade VARCHAR(5) NOT NULL,
    grade_points_earned INTEGER NOT NULL
);
```

### Grade Changes Table (Audit Trail)

```sql
CREATE TABLE grade_changes (
    id SERIAL PRIMARY KEY,
    regno VARCHAR(20) NOT NULL,
    subject_code VARCHAR(20) NOT NULL,
    semester INTEGER NOT NULL,
    original_grade VARCHAR(5) NOT NULL,
    new_grade VARCHAR(5) NOT NULL,
    credits INTEGER NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 API Endpoints

### Public Endpoints

- `GET /` - Student search page
- `GET /auth/{regno}` - Authentication form
- `POST /auth/{regno}` - Login submission
- `GET /{regno}/` - Student results page (authenticated)
- `GET /pdf/{regno}/{filename}` - PDF viewer
- `GET /zip/{regno}` - Download all PDFs as ZIP

### API Endpoints

- `POST /api/save-grade-change` - Save grade modifications
- `GET /api/grade-changes/{regno}` - Get student's grade changes
- `GET /api/grade-changes` - Get all grade changes (admin)

### Administrative

- `GET /admin/grade-changes` - Admin dashboard

## 🎯 Usage Guide

### For Students

1. **Search & Access**

   - Visit the homepage
   - Search for your registration number or name
   - Click on your registration number

2. **Authentication**

   - Enter your date of birth (DD-MM-YYYY format)
   - Click "Login" to access your results

3. **View Results**

   - Browse through your semester results
   - View individual PDF files
   - Download all results as a ZIP file

4. **Modify Grades**
   - Click on any grade dropdown to change it
   - Changes are saved automatically
   - Updated GPA is calculated instantly
   - Changes persist on page reload

### For Administrators

1. **Monitor Changes**

   - Visit `/admin/grade-changes`
   - View all recent grade modifications
   - Monitor student activity patterns

2. **API Access**
   - Use REST APIs for data integration
   - Export grade change data
   - Generate analytics reports

## 🔒 Security Features

### Authentication

- Session-based authentication
- DOB verification for student access
- Protected routes and PDF access
- Automatic session timeout

### Data Protection

- SQL injection prevention
- Input validation and sanitization
- Error handling without data exposure
- Secure file serving

### Audit Trail

- Complete grade change history
- Timestamp tracking for all modifications
- Original data preservation
- Administrative monitoring capabilities

## 🎨 Styling & Theming

### Dark Mode

- Automatic detection of system preference
- Smooth transitions between themes
- Optimized for both light and dark environments

### Responsive Design

- Mobile-first approach
- Tablet and desktop optimizations
- Touch-friendly interface elements
- Consistent experience across devices

### Modern UI Elements

- Glass morphism effects
- Gradient backgrounds
- Smooth animations
- Interactive feedback

## 🚀 Deployment

### Local Development

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment

#### Using Render (Recommended)

1. Connect your GitHub repository to Render
2. Use the provided `render.yaml` configuration
3. Set environment variables in Render dashboard
4. Deploy automatically on code changes

#### Using Docker

```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Environment Variables for Production

```env
DATABASE_URL=your_production_database_url
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
STORAGE_BUCKET_NAME=your_bucket_name
```

## 📊 Grade Change Tracking System

### How It Works

1. **Detection**: JavaScript automatically detects grade changes
2. **Validation**: Backend validates changes and student existence
3. **Storage**: Changes saved to separate audit table
4. **Display**: Updated grades shown on page reload
5. **History**: Complete audit trail maintained

### Benefits

- **Transparency**: Full visibility into grade modifications
- **Accountability**: Track who changed what and when
- **Flexibility**: Allow corrections without affecting original data
- **Analytics**: Understand grade change patterns

## 🛠️ Development

### Adding New Features

1. **Database Changes**

   - Modify `database.py` for new models
   - Create migration scripts for schema updates
   - Update API endpoints as needed

2. **Frontend Updates**

   - Edit HTML templates in `templates/` directory
   - Update CSS in `static/style.css`
   - Add JavaScript for interactivity

3. **API Extensions**
   - Add new endpoints in `main.py`
   - Include proper validation and error handling
   - Update documentation

### Code Structure

- **main.py**: FastAPI application and route handlers
- **database.py**: SQLAlchemy models and database configuration
- **templates/**: Jinja2 HTML templates
- **static/**: CSS, JavaScript, and other assets

## 🔮 Future Enhancements

### Planned Features

- **Email Notifications**: Alert on grade changes
- **Bulk Operations**: Mass grade updates
- **Advanced Analytics**: Detailed reporting dashboard
- **Mobile App**: Native mobile application
- **SSO Integration**: Single sign-on support

### Technical Improvements

- **Caching**: Redis for performance optimization
- **Background Tasks**: Celery for async processing
- **Rate Limiting**: API protection against abuse
- **Logging**: Enhanced application monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Common Issues

**Database Connection Issues**

- Verify environment variables are correctly set
- Check database credentials and connectivity
- Ensure Supabase project is active

**PDF Not Loading**

- Verify Supabase Storage configuration
- Check bucket permissions and file paths
- Ensure service key has proper access

**Grade Changes Not Persisting**

- Run the grade changes migration script
- Check database table creation
- Verify API endpoint functionality

### Getting Help

- Open an issue on GitHub
- Check the documentation
- Review the logs for error messages

## 📈 Performance Tips

### Database Optimization

- Index frequently queried columns
- Use connection pooling for high traffic
- Implement database query optimization

### Frontend Performance

- Enable gzip compression
- Optimize images and assets
- Use CDN for static files

### Monitoring

- Set up application monitoring
- Track response times and errors
- Monitor database performance

---

Built with ❤️ using FastAPI, SQLAlchemy, and modern web technologies.
