using Common.DTOs;

namespace Common.Entities
{
    public enum Genders
    {
        Unspecified = 0,
        Male = 1,
        Female = 2,
    }
    
    public class Employee
    {
        // Identifier Field

        public int Id { get; set; }
        public string UserIdentity { get; set; } = string.Empty;

        // Authentication Fields

        public Int16 ? AuthType { get; set; }
        public string Password { get; set; } = string.Empty;
        public Int16 ? HashType { get; set; }
        public string HashSalt { get; set; } = string.Empty;

        // Normal Information Fields

        public string FirstName { get; set; } = string.Empty;
        public string MiddleName { get; set; } = string.Empty;
        public string LastName { get; set; } = string.Empty;
        public string FullName { get; set; } = string.Empty;
        public Genders Gender { get; set; } = Genders.Unspecified;
        public string Email { get; set; } = string.Empty;
        public string ? PhoneNumber { get; set; }
        public DateTime OnboardDate { get; set; }
        public Int16 DayOfBirth { get; set; }
        public Int16 MonthOfBirth { get; set; }
        public byte[] ? ProfilePhoto { get; set; }
        public bool ExcludeFromCelebration { get; set; }
        public Int16 Status { get; set; 
        }
        
        // Relational Fields

        public Int16 DepartmentId { get; set; }

        // FK to Department

        public string DepartmentName { get; set; } = string.Empty;
        public Int16 DepartmentStatus { get; set; }
        public Int16 TitleId { get; set; }
        
        // FK to Title

        public string TitleName { get; set; } = string.Empty;
        public Int16 TitleStatus { get; set; }

        // Mapping Methods

        public EmployeeMainViewDto ToEmployeeMainViewDto() => new EmployeeMainViewDto()
        {
            Id = this.Id,
            UserIdentity = this.UserIdentity,
            FirstName = this.FirstName,
            MiddleName = this.MiddleName,
            LastName = this.LastName,
            FullName = this.FullName,
            Email = this.Email,
            OnboardDate = this.OnboardDate,
            Status = this.Status,
            DepartmentId = this.DepartmentId,
            DepartmentName = this.DepartmentName,
            TitleId = this.TitleId,
            TitleName = this.TitleName,
        };
    }
}