using System.Data.Common;

namespace DataAccessLayer.DbContext
{
    public abstract class DatabaseContext
    {
        protected DbConnection ? connection;
        protected String connectionString;
        protected DatabaseContext(String conectionString)
        {
            this.connectionString = conectionString;
        }
        public abstract Task<DbDataReader> ExecuteReaderAsync(String sql, Dictionary<String, Object> ? parameters = null);
        public abstract Task<Object?> ExecuteScalarAsync(String sql, Dictionary<String, Object> ? parameters = null);
        public abstract Task<int> ExecuteQueryAsync(String sql, Dictionary<String, Object> ? parameters = null);
        public abstract Task<bool> CloseAsync();
        public abstract Task<bool> OpenAsync();
    }
}