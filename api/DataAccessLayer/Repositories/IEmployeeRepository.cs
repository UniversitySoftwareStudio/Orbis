using Common.Entities;

namespace DataAccessLayer.Repositories
{
    public interface IEmployeeRepository: IBaseRepository
    {
        Task < List < Employee >> GetAllAsync();
        Task < Employee ? > GetByIdAsync(int id);
        Task < int > AddAsync(Employee employee);
        Task < Employee > UpdateAsync(Employee employee);
    }
}