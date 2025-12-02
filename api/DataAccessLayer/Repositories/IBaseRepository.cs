namespace DataAccessLayer.Repositories
{
    public interface IBaseRepository
    {
        public Task<bool> OpenAsync();
        public Task<bool> CloseAsync();
    }
}