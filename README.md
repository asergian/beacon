# Beacon: Email Processing Application
A streamlined email assistant that prioritizes what matters, declutters your inbox, and keeps you effortlessly on top of tasks.

This application is an email processing system that analyzes emails using Natural Language Processing (NLP) and Large Language Model (LLM) capabilities. It extracts key information, calculates priorities, and handles errors effectively, utilizing OpenAI's language model and spaCy for NLP.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Installation

To set up the application, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/asergian/beacon.git
   ```
2. Navigate to the project directory:
   ```bash
   cd email-processing-app
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables in a `.env` file:
   ```plaintext
   OPENAI_API_KEY=your_openai_api_key
   IMAP_SERVER=your_imap_server
   EMAIL=your_email@example.com
   IMAP_PASSWORD=your_email_password
   LOGGING_LEVEL=DEBUG
   ```

## Usage

To run the application, execute the following command:

```bash
python app.py
```

Once the application is running, you can access it in your web browser at `http://localhost:5000`.

### API Endpoints

- **Home**: `/` - Renders the home page.
- **Email Summaries**: `/emails` - Displays a summary of recent emails.
- **Test Connection**: `/test-connection` - Tests the email connection and fetches emails.
- **Test Analysis**: `/test-analysis` - Fetches, parses, and analyzes emails.

## Documentation

Comprehensive documentation for Beacon is available in the [docs/](docs/) directory:

- [**Architecture Overview**](docs/ARCHITECTURE.md): High-level system design and components
- [**Email Processing Pipeline**](docs/email_processing.md): How emails are processed and analyzed
- [**Memory Management**](docs/memory_management.md): Memory optimization techniques used
- **API Documentation**: Generated using Sphinx and available at `docs/sphinx/build/html/index.html` after building

To build the API documentation:

```bash
cd docs/sphinx
make html
```

Module-specific documentation can be found in README.md files within each module directory.

## Features

- **Email Analysis**: Uses OpenAI's LLM to analyze email content and extract actionable items.
- **NLP Integration**: Utilizes spaCy for natural language processing to enhance email understanding.
- **Priority Calculation**: Automatically calculates email priorities based on urgency and sender importance.
- **Error Handling**: Robust error handling for email fetching and processing.
- **Memory Management**: Implements subprocess isolation for NLP tasks to optimize memory usage in resource-constrained environments.

### Memory Management Strategy

This application uses a subprocess-based approach for memory-intensive NLP operations:

1. **Process Isolation**: SpaCy models are loaded in separate processes to prevent memory leaks and fragmentation.
2. **Memory Optimization**: NLP components are selectively enabled to minimize the memory footprint.
3. **Garbage Collection**: Explicit memory cleanup is performed after processing.
4. **Resource Monitoring**: Memory usage is logged at various stages to track consumption patterns.

To switch between memory management strategies:

- Standard in-process analyzer: `ContentAnalyzer` (uses more memory but slightly faster)
- Subprocess-based analyzer: `ContentAnalyzerSubprocess` (better memory isolation, recommended for production)

The default configuration uses the subprocess approach to maintain stable memory usage, which is especially important for servers with limited resources.

## Contributing

Contributions are welcome! To contribute to the project, please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes and commit them (`git commit -m 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Open a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

Your Name - [alex.sergian@gmail.com](mailto:alex.sergian@gmail.com)

Project Link: [https://github.com/asergian/beacon](https://github.com/asergian/beacon)

# Beacon Email Application

Beacon is an intelligent email management application that helps users organize, prioritize, and respond to emails efficiently.

## Features

- Email analysis and prioritization
- Custom categories and tagging
- Action item extraction
- Email response system with rich text editor
- Light and dark theme support

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis (optional, for caching)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/beacon.git
   cd beacon
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory with the following variables:
   ```
   # Flask Configuration
   FLASK_APP=app
   FLASK_ENV=development
   FLASK_DEBUG=1
   FLASK_SECRET_KEY=your-secret-key

   # Database Configuration
   DATABASE_URL=postgresql://username:password@localhost/beacon

   # Email Configuration (IMAP for receiving)
   IMAP_SERVER=imap.gmail.com
   EMAIL=your-email@gmail.com
   IMAP_PASSWORD=your-app-password

   # Email Configuration (SMTP for sending)
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_TLS=1
   # Use the same email and password as IMAP by default
   # SMTP_EMAIL=your-email@gmail.com
   # SMTP_PASSWORD=your-app-password

   # OpenAI Configuration (if using AI features)
   OPENAI_API_KEY=your-openai-api-key
   ```

5. Initialize the database:
   ```
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. Run the application:
   ```
   flask run
   ```

## Email Sending Setup

To enable email sending functionality, you need to configure your email account for SMTP access:

### Gmail Setup

1. Enable 2-Step Verification for your Google account
2. Generate an App Password:
   - Go to your Google Account settings
   - Select "Security"
   - Under "Signing in to Google," select "App passwords"
   - Generate a new app password for "Mail" and "Other (Custom name)"
   - Use this password as your `SMTP_PASSWORD` in the `.env` file

### Other Email Providers

For other email providers, you'll need to:
1. Find the SMTP server address and port
2. Check if TLS is required
3. Set up app-specific passwords if 2FA is enabled

## Usage

1. Log in to the application
2. Navigate to the email inbox to view and manage emails
3. Use the settings page to customize your experience
4. Respond to emails using the built-in editor

## Development

### Project Structure

- `app/` - Main application package
  - `email/` - Email processing modules
  - `routes/` - API routes and views
  - `static/` - Static assets (CSS, JS)
  - `templates/` - HTML templates
  - `models.py` - Database models
  - `config.py` - Application configuration

### Adding New Features

1. Create a new branch for your feature
2. Implement the feature
3. Write tests
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
