namespace Common.DTOs
{
    public class EmployeeMainViewDto
    {
        // Identifier Field
  
        public int Id { get; set; }
        public string? UserIdentity { get; set; }
  
        // Normal Information Fields
  
        public string? FirstName { get; set; }
        public string? MiddleName { get; set; }
        public string? LastName { get; set; }
        public string? FullName { get; set; }
        public string? Email { get; set; }
        public DateTime OnboardDate { get; set; }
        public Int16 Status { get; set; }
  
        // Relational Fields
  
        public Int16 DepartmentId { get; set; }
  
         // FK to Department
  
        public string DepartmentName { get; set; } = string.Empty;
        public Int16 TitleId { get; set; }
  
        // FK to Title
  
        public string TitleName { get; set; } = string.Empty; 
    }
}