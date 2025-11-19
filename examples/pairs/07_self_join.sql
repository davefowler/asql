-- Self-join: Employee hierarchy
SELECT 
    e1.employee_id,
    e1.employee_name,
    e1.department,
    e2.employee_name AS manager_name,
    e2.department AS manager_department
FROM employees e1
LEFT JOIN employees e2 ON e1.manager_id = e2.employee_id
WHERE e1.status = 'active'
ORDER BY e1.department, e1.employee_name;

