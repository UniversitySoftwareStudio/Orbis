using Common.Entities;

namespace BusinessLayer.Services
{
    public interface IEmployeeService
    {
        Task<ServiceResult<List<Employee>>> GetAll();
        //Task<ServiceResult<Employee?>> GetById(int id);
        //Task<ServiceResult<int>> Add(Employee employee);
        //Task<ServiceResult<Employee>> Update(Employee employee);
    }
}