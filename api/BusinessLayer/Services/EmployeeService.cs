using Common.Entities;
using DataAccessLayer.Repositories;

namespace BusinessLayer.Services
{
    internal class EmployeeService: IEmployeeService
    {
        private readonly IEmployeeRepository _employeeRepository;

        public EmployeeService(IEmployeeRepository employeeRepository)
        {
            _employeeRepository = employeeRepository;
        }
        
        public async Task<ServiceResult<List<Employee>>> GetAll()
        {
            var employees = await _employeeRepository.GetAllAsync();
            await _employeeRepository.CloseAsync();
            return new ServiceResult<List<Employee>>
            {
                Data = employees,
                StatusCode = 200,
                Success = true
            };
        }
    }
}