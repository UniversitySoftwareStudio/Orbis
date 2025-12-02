using DataAccessLayer.DbContext;
using Common.Entities;

namespace DataAccessLayer.Repositories
{
    internal class EmployeeRepository: BaseRepository, IEmployeeRepository
    {
        private readonly DatabaseContext _dbContext;

        public EmployeeRepository(DatabaseContext databaseContext): base(databaseContext)
        {
            _dbContext = databaseContext;
        }

        public async Task<List<Employee>> GetAllAsync()
        {
            var sqlQuery = @"
            SELECT
                e.id, e.user_identity, e.first_name, e.middle_name, e.last_name,
                CONCAT_WS(' ', first_name, middle_name, last_name) AS full_name,
                e.email, e.onboard_date, e.status,
                d.id AS department_id, d.department_name AS department_name,
                t.id AS title_id, t.position_name AS title_name FROM public.t_employees e
            JOIN
                public.t_departments d ON e.department_id = d.id
            JOIN
                public.t_positions t ON e.title_id = t.id
            WHERE
                e.status <> 3;
            ";
            var employees = new List<Employee> ();
            await using var reader = await _dbContext.ExecuteReaderAsync(sqlQuery);
            while (await reader.ReadAsync())
            {
                employees.Add(new Employee
                {
                    Id = (int) reader["id"],
                    UserIdentity = (string) reader["user_identity"],
                    FirstName = (string) reader["first_name"],
                    MiddleName = DBNull.Value.Equals(reader["middle_name"]) ? string.Empty : (string) reader["middle_name"],
                    LastName = (string) reader["last_name"],
                    FullName = (string) reader["full_name"],
                    Email = (string) reader["email"],
                    OnboardDate = (DateTime) reader["onboard_date"],
                    Status = (short) reader["status"],
                    DepartmentId = (short) reader["department_id"],
                    DepartmentName = (string) reader["department_name"],
                    TitleId = (short) reader["title_id"],
                    TitleName = (string) reader["title_name"],
                });
            }
            return employees;
        }

        public async Task<Employee?> GetByIdAsync(int id)
        {
            var sql = @"
            SELECT
                e.id, e.user_identity, e.first_name, e.middle_name, e.last_name,
                CONCAT_WS(' ', e.first_name, e.middle_name, e.last_name) AS full_name,
                e.gender, e.email, e.phone_number, e.onboard_date, e.day_of_birth, e.month_of_birth,
                e.profile_photo, e.exclude_from_celebration, e.status,
                d.id AS department_id, d.department_name AS department_name,
                d.status AS department_status,
                t.id AS title_id, t.position_name AS title_name, t.status AS title_status
            FROM
                public.t_employees e
            JOIN
                public.t_departments d ON e.department_id = d.id AND d.status <> 3
            JOIN
                public.t_positions t ON e.title_id = t.id AND t.status <> 3
            WHERE
                e.id = @id AND e.status <> 3;
            ";
            var parameters = new Dictionary<string, object> () { { "id", id } };
            await using var reader = await _dbContext.ExecuteReaderAsync(sql, parameters);
            if (await reader.ReadAsync())
            {
                return new Employee()
                {
                    Id = (int) reader["id"],
                    UserIdentity = (string) reader["user_identity"],
                    FirstName = (string) reader["first_name"],
                    MiddleName = DBNull.Value.Equals(reader["middle_name"]) ? string.Empty : (string) reader["middle_name"],
                    LastName = (string) reader["last_name"],
                    FullName = (string) reader["full_name"],
                    Gender = (Genders)(Int16) reader["gender"],
                    Email = (string) reader["email"],
                    PhoneNumber = DBNull.Value.Equals(reader["phone_number"]) ? string.Empty : (string) reader["phone_number"],
                    OnboardDate = (DateTime) reader["onboard_date"],
                    DayOfBirth = (short) reader["day_of_birth"],
                    MonthOfBirth = (short) reader["month_of_birth"],
                    ProfilePhoto = DBNull.Value.Equals(reader["profile_photo"]) ? new byte[0] : (byte[]) reader["profile_photo"],
                    ExcludeFromCelebration = (bool) reader["exclude_from_celebration"],
                    Status = (short) reader["status"],
                    DepartmentId = (short) reader["department_id"],
                    DepartmentName = (string) reader["department_name"],
                    DepartmentStatus = (short) reader["department_status"],
                    TitleId = (short) reader["title_id"],
                    TitleName = (string) reader["title_name"],
                    TitleStatus = (short) reader["title_status"],
                };
            }
            return null;
        }

        public async Task<int> AddAsync(Employee employee)
        {
            var sql = @"
            SELECT public.sp_add_employee
            (
                @user_identity::character varying,
                @first_name::character varying,
                @middle_name::character varying,
                @last_name::character varying,
                @gender::smallint,
                @email::character varying,
                @phone_number::character varying,
                @onboard_date::date,
                @day_of_birth::smallint,
                @month_of_birth::smallint,
                @profile_photo::bytea,
                @exclude_from_celebration::boolean,
                @department_id::integer,
                @title_id::integer
            )";
            Dictionary<String, Object> parameters = new()
            {
                {"user_identity", employee.UserIdentity},
                {"first_name", employee.FirstName},
                {"middle_name", employee.MiddleName},
                {"last_name", employee.LastName},
                {"gender", (Int16) employee.Gender},
                {"email", employee.Email},
                {"phone_number", employee.PhoneNumber == null ? DBNull.Value : employee.PhoneNumber},
                {"onboard_date", employee.OnboardDate},
                {"day_of_birth", employee.DayOfBirth},
                {"month_of_birth", employee.MonthOfBirth},
                {"profile_photo", employee.ProfilePhoto == null ? DBNull.Value : employee.ProfilePhoto},
                {"exclude_from_celebration", employee.ExcludeFromCelebration},
                {"department_id", employee.DepartmentId},
                {"title_id", employee.TitleId}
            };
            return (int)(await _dbContext.ExecuteScalarAsync(sql, parameters)) !;
        }
        
        public async Task<Employee> UpdateAsync(Employee employee)
        {
            var sql = @"
            SELECT public.sp_update_employee
            (
                @id::integer,
                @first_name::character varying,
                @middle_name::character varying,
                @last_name::character varying,
                @gender::smallint,
                @email::character varying,
                @phone_number::character varying,
                @onboard_date::date,
                @day_of_birth::smallint,
                @month_of_birth::smallint,
                @profile_photo::bytea,
                @exclude_from_celebration::boolean,
                @status::smallint,
                @department_id::integer,
                @title_id::integer
            )";
            Dictionary<String, Object> parameters = new Dictionary<String, Object> ()
            {
                {"id", employee.Id},
                {"first_name", employee.FirstName},
                {"middle_name", employee.MiddleName},
                {"last_name", employee.LastName},
                {"gender", (Int16) employee.Gender},
                {"email", employee.Email},
                {"phone_number", employee.PhoneNumber == null ? DBNull.Value : employee.PhoneNumber},
                {"onboard_date", employee.OnboardDate},
                {"day_of_birth", employee.DayOfBirth},
                {"month_of_birth", employee.MonthOfBirth},
                {"profile_photo", employee.ProfilePhoto == null ? DBNull.Value : employee.ProfilePhoto},
                {"exclude_from_celebration", employee.ExcludeFromCelebration},
                {"status", (Int16) employee.Status},
                {"department_id", employee.DepartmentId},
                {"title_id", employee.TitleId}
            };
            employee.Id = (int)(await _dbContext.ExecuteScalarAsync(sql, parameters)) !;
            return employee;
        }
    }
}