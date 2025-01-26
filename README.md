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
   git clone https://github.com/yourusername/email-processing-app.git
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

## Features

- **Email Analysis**: Uses OpenAI's LLM to analyze email content and extract actionable items.
- **NLP Integration**: Utilizes spaCy for natural language processing to enhance email understanding.
- **Priority Calculation**: Automatically calculates email priorities based on urgency and sender importance.
- **Error Handling**: Robust error handling for email fetching and processing.

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

Your Name - [your.email@example.com](mailto:your.email@example.com)

Project Link: [https://github.com/yourusername/email-processing-app](https://github.com/yourusername/email-processing-app)
