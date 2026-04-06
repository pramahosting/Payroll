-- Create all service databases
CREATE DATABASE employee_db;
CREATE DATABASE timesheet_db;
CREATE DATABASE payroll_db;
CREATE DATABASE compliance_db;
CREATE DATABASE payments_db;
CREATE DATABASE reporting_db;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE employee_db TO payroll;
GRANT ALL PRIVILEGES ON DATABASE timesheet_db TO payroll;
GRANT ALL PRIVILEGES ON DATABASE payroll_db TO payroll;
GRANT ALL PRIVILEGES ON DATABASE compliance_db TO payroll;
GRANT ALL PRIVILEGES ON DATABASE payments_db TO payroll;
GRANT ALL PRIVILEGES ON DATABASE reporting_db TO payroll;
