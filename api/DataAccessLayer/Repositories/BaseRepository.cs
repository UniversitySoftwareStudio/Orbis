using DataAccessLayer.DbContext;

namespace DataAccessLayer.Repositories
{
    public class BaseRepository: IBaseRepository
    {
        private readonly DatabaseContext _dbContext;

        public BaseRepository(DatabaseContext databaseContext)
        {
            this._dbContext = databaseContext;
        }

        public async Task < bool > OpenAsync()
        {
            try { await _dbContext.OpenAsync(); }
            catch { return false; }
            return true;
        }
        
        public async Task < bool > CloseAsync()
        {
            try { await _dbContext.CloseAsync(); }
            catch { return false; }
            return true;
        }
    }
}