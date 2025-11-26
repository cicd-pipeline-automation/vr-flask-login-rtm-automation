/**************************************************************
 🏗️  JENKINS PIPELINE — FLASK LOGIN → RTM → JIRA → CONFLUENCE
 📌 Purpose:
     • Execute automated tests
     • Generate HTML + PDF test reports
     • Upload test results to RTM
     • Attach formatted reports to Jira Test Execution
     • Publish reports to Confluence
     • Notify stakeholders via email
**************************************************************/

pipeline {
    agent any

    /**********************************************************
     ⚙ PIPELINE OPTIONS
    **********************************************************/
    options {
        timestamps()                     // Accurate timed logs
        disableConcurrentBuilds()        // No overlapping runs
        skipDefaultCheckout()            // Manual SCM checkout
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    /**********************************************************
     🔐 GLOBAL ENVIRONMENT VARIABLES
    **********************************************************/
     environment {

        /* ------------------ SMTP Email ------------------ */
        SMTP_HOST       = credentials('smtp-host2')
        SMTP_PORT       = '25'
        SMTP_USER       = credentials('smtp-user2')
        SMTP_PASS       = credentials('smtp-pass2')
        REPORT_FROM     = credentials('sender-email')
        REPORT_TO       = credentials('receiver-email')
        REPORT_CC       = credentials('cc-email')
        REPORT_BCC      = credentials('bcc-email')

        /* ---------------- Confluence Access -------------- */
        CONFLUENCE_BASE  = credentials('confluence-base3')
        CONFLUENCE_USER  = credentials('confluence-user')
        CONFLUENCE_TOKEN = credentials('confluence-token')
        CONFLUENCE_SPACE = "Jenkins"
        CONFLUENCE_TITLE = "Test Result Report"

        /* ------------------- Jira + RTM ------------------- */
        JIRA_URL        = credentials('jira-base-url')
        JIRA_USER       = credentials('jira-user')
        JIRA_API_TOKEN  = credentials('jira-token')

        RTM_API_TOKEN   = credentials('rtm-api-key')
        RTM_BASE_URL    = credentials('rtm-base-url')
        PROJECT_KEY     = "CR0B"

        /* ---------------- GitHub Checkout ---------------- */
        GITHUB_CREDENTIALS = credentials('github-credentials')

        /* ---------------- Reporting Paths ---------------- */
        REPORT_DIR        = 'report'
        TEST_RESULTS_DIR  = 'report'
        TEST_RESULTS_ZIP  = 'test-results.zip'

        /* ---------------- Python Configuration ----------- */
        VENV_PATH         = "C:\\jenkins_work\\venv"
        PIP_CACHE_DIR     = "C:\\jenkins_home\\pip-cache"
        PYTHONUTF8        = '1'
        PYTHONLEGACYWINDOWSSTDIO = '1'

        FORCE_FAIL = false
    }

    /**********************************************************
     🧑‍🔧 USER PARAMETERS
    **********************************************************/
    // parameters {
    //     string(
    //         name: 'RTM_TRIGGERED_BY',
    //         defaultValue: 'devopsuser8413',
    //         description: 'RTM user who initiated this execution'
    //     )
    // }

    /**********************************************************
     🚀 PIPELINE STAGES
    **********************************************************/
    stages {

        /* ==================================================
         1) CHECKOUT SOURCE CODE
        ================================================== */
        stage('Checkout Source Code') {
            steps {
                echo "📦 Checking out source repository..."
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/Automation-Jenkins-RTM']],
                    userRemoteConfigs: [[
                        url: 'https://github.com/ReTechnologies/Jenkins-CICD-Pipeline.git',
                        credentialsId: 'github-credentials'
                    ]]
                ])
            }
        }

        /* ==================================================
         2) PREPARE PYTHON ENVIRONMENT
        ================================================== */
        stage('Setup Python Environment') {
            steps {
                echo "🐍 Setting up Python virtual environment..."
                bat """
                    @echo off
                    if not exist "%VENV_PATH%" (
                        echo Creating virtual environment...
                        C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe -m venv "%VENV_PATH%"
                    )
                    "%VENV_PATH%\\Scripts\\pip.exe" install --upgrade pip setuptools wheel ^
                        --cache-dir "%PIP_CACHE_DIR%"
                """
            }
        }
        
        /* ==================================================
         3) INSTALL PYTHON REQUIREMENTS
        ================================================== */
        stage('Install Python Dependencies') {
            steps {
                echo "📥 Installing required Python modules..."
                bat """
                    "%VENV_PATH%\\Scripts\\pip.exe" install -r requirements.txt ^
                        --cache-dir "%PIP_CACHE_DIR%"
                """
            }
        }

        /* ==================================================
         4) RUN TESTS + PRODUCE JUNIT XML
        ================================================== */
        stage('Run Tests & Generate JUnit Report') {
            steps {
                echo "🧪 Executing test suite..."
                bat """
                    if not exist report mkdir report

                    "%VENV_PATH%\\Scripts\\pytest.exe" ^
                        --junitxml=report/junit.xml ^
                        --log-file=report/pytest_output.txt ^
                        --log-file-level=INFO ^
                        --html=report/report.html ^
                        --self-contained-html
                """
            }
        }

        /* ==================================================
         5) GENERATE CUSTOM HTML + PDF REPORTS
        ================================================== */
        stage('Generate Final Test Report') {
            steps {
                echo "📝 Generating enhanced HTML/PDF reports..."
                bat """
                    "%VENV_PATH%\\Scripts\\python.exe" scripts/generate_report.py
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: 'report/test_result_report_v*.html'
                    archiveArtifacts artifacts: 'report/test_result_report_v*.pdf'
                    archiveArtifacts artifacts: 'report/version.txt'
                }
            }
        }

        /* ==================================================
         6) PUBLISH REPORT TO CONFLUENCE
        ================================================== */
        stage('Publish Report to Confluence') {
            steps {
                echo "🌐 Publishing report to Confluence..."
                bat """
                    "%VENV_PATH%\\Scripts\\python.exe" scripts/publish_report_confluence.py
                """
            }
        }

        /* ==================================================
         7) ATTACH HTML/PDF REPORTS → JIRA TEST EXECUTION
        ================================================== */
        stage('Attach Reports to RTM/Jira') {
            steps {
                echo "📎 Attaching PDF/HTML to Jira Test Execution..."

                script {
                    // Read version
                    def version = readFile("report/version.txt").trim()
                    echo "ℹ Detected report version: v${version}"

                    // Read Jira/RTM Execution Key
                    def issueKey = readFile("rtm_execution_key.txt").trim()
                    echo "🔑 Jira Issue Key: ${issueKey}"

                    env.REPORT_VERSION = version
                    env.RTM_ISSUE_KEY = issueKey

                    def pdfFile  = "report/test_result_report_v${version}.pdf"
                    def htmlFile = "report/test_result_report_v${version}.html"

                    echo "📄 PDF Path  : ${pdfFile}"
                    echo "🌐 HTML Path : ${htmlFile}"
                }

                bat """
                    "%VENV_PATH%\\Scripts\\python.exe" scripts\\rtm_attach_reports.py ^
                    --issueKey "%RTM_ISSUE_KEY%" ^
                    --pdf "report/test_result_report_v%REPORT_VERSION%.pdf" ^
                    --html "report/test_result_report_v%REPORT_VERSION%.html"
                """
            }
        }

        /* ==================================================
         8) EMAIL REPORT TO STAKEHOLDERS
        ================================================== */
        stage('Email Report') {
            steps {
                echo "📧 Sending email notification..."
                echo "Using PDF_REPORT_PATH = ${env.PDF_REPORT_PATH}"
                bat """
                    "%VENV_PATH%\\Scripts\\python.exe" scripts/send_report_email.py
                """
            }
        }

        /* ==================================================
         9) PACKAGE TEST RESULTS ZIP
        ================================================== */
        stage('Archive Test Results') {
            steps {
                echo "📦 Creating ZIP archive of test results..."
                powershell """
                    if (Test-Path ${env.TEST_RESULTS_ZIP}) { Remove-Item ${env.TEST_RESULTS_ZIP} }
                    Add-Type -AssemblyName System.IO.Compression.FileSystem
                    [IO.Compression.ZipFile]::CreateFromDirectory('${env.TEST_RESULTS_DIR}', '${env.TEST_RESULTS_ZIP}')
                """
            }
            post {
                success {
                    archiveArtifacts artifacts: "${TEST_RESULTS_ZIP}"
                }
            }
        }

        /* ==================================================
         🔟 UPLOAD TEST RESULTS TO RTM
        ================================================== */
        stage('Upload JUnit ZIP to RTM') {
            steps {
                echo "📤 Uploading JUnit ZIP to RTM..."
                bat """
                    "%VENV_PATH%\\Scripts\\python.exe" scripts\\rtm_upload_results.py ^
                    --archive "test-results.zip" ^
                    --rtm-base "%RTM_BASE_URL%" ^
                    --project "%PROJECT_KEY%" ^
                    --job-url "%BUILD_URL%"
                """
            }
        }
    }

    /**********************************************************
     🧹 POST-BUILD ACTIONS
    **********************************************************/
    post {
        success { echo "🎉 Pipeline completed successfully." }
        failure { echo "❌ Pipeline failed — please check logs." }
        always  { echo "🧹 Workspace cleanup completed." }
    }
}
