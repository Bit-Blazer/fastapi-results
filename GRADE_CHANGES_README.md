# Grade Change Tracking System

This system automatically tracks when students modify their grades using the dropdown selectors on the student results page.

## 🚀 Setup Instructions

### 1. Database Migration

Run the migration script to add the new `grade_changes` table:

```bash
python add_grade_changes_table.py
```

This will create a table with the following structure:

- `id` - Primary key
- `regno` - Student registration number
- `subject_code` - Subject code that was changed
- `semester` - Semester number
- `original_grade` - The original grade before change
- `new_grade` - The new grade after change
- `credits` - Subject credits
- `changed_at` - Timestamp of when the change occurred

### 2. API Endpoints

The system provides several API endpoints:

#### Save Grade Change

- **POST** `/api/save-grade-change`
- Automatically called when a student changes a grade
- Saves the change to the database

#### View Student Grade Changes

- **GET** `/api/grade-changes/{regno}`
- View all grade changes for a specific student
- Example: `/api/grade-changes/113222031001`

#### View All Grade Changes (Admin)

- **GET** `/api/grade-changes`
- View all grade changes across all students
- Supports pagination with `limit` and `offset` parameters
- Example: `/api/grade-changes?limit=50&offset=0`

### 3. Admin Dashboard

Visit `/admin/grade-changes` to access the administrative dashboard where you can:

- View all recent grade changes
- Search for changes by specific students
- Monitor statistics (total changes, daily changes, etc.)
- Export data for analysis

## 🔧 How It Works

### Frontend Integration

The grade change tracking is automatically integrated into the existing student results page (`student.html`):

1. **Automatic Detection**: When a student changes a grade using the dropdown, the system detects the change
2. **Data Collection**: Captures the registration number, subject code, semester, original grade, new grade, and credits
3. **API Call**: Sends the data to the backend API endpoint
4. **User Feedback**: Shows a success/error notification to the user

### Backend Processing

1. **Validation**: Verifies that the student exists in the database
2. **Storage**: Saves the grade change record with timestamp
3. **Response**: Returns success/failure status to the frontend

### Data Integrity

- Each grade change is logged with a timestamp
- Original grades are preserved for audit purposes
- Changes are linked to student registration numbers
- Duplicate prevention through unique constraints

## 📊 Usage Examples

### For Students

Students simply change grades using the existing dropdown menus. The system automatically tracks these changes in the background without any additional user action required.

### For Administrators

1. **Monitor Recent Changes**:

   ```
   GET /api/grade-changes?limit=20
   ```

2. **Check Specific Student**:

   ```
   GET /api/grade-changes/113222031001
   ```

3. **Access Admin Dashboard**:
   Visit: `http://your-domain.com/admin/grade-changes`

## 🛡️ Security Considerations

- Grade changes are logged but don't affect the original PDF records
- All changes are timestamped for audit trails
- Student verification should be implemented if needed
- Consider implementing rate limiting for API endpoints
- Add authentication for admin endpoints in production

## 📈 Monitoring & Analytics

The system enables you to:

- Track which grades are most frequently changed
- Identify patterns in grade modifications
- Monitor student engagement with the system
- Generate reports for academic administrators

## 🔮 Future Enhancements

Potential improvements:

- Email notifications for grade changes
- Bulk export to CSV/Excel
- Advanced filtering and search options
- Integration with academic calendars
- Grade change approval workflows
- Student notification system

## 📝 Notes

- Grade changes are saved automatically without affecting GPA calculations in real-time
- The system maintains a complete audit trail of all modifications
- Original PDF records remain unchanged
- Changes are stored separately for transparency and auditing
