using Npgsql;
using System.Data.Common;

namespace DataAccessLayer.DbContext
{
    public class PgDatabaseContext: DatabaseContext
    {
        public PgDatabaseContext(string conectionString): base(conectionString)
        {
            connection = new NpgsqlConnection(conectionString);
        }

        public override async Task<DbDataReader> ExecuteReaderAsync(string sql, Dictionary<string, object> ? parameters = null)
        {
            if (connection!.State != System.Data.ConnectionState.Open)
            {
                await connection.OpenAsync();
            }
            NpgsqlCommand cmd = (NpgsqlCommand) connection!.CreateCommand();
            cmd.CommandText = sql;
            if (parameters != null && parameters.Count > 0)
            {
                foreach(var parameter in parameters)
                {
                    cmd.Parameters.AddWithValue(parameter.Key, parameter.Value);
                }
            }
            return await cmd.ExecuteReaderAsync();
        }

        public override async Task<object?> ExecuteScalarAsync(string sql, Dictionary<string, object> ? parameters = null)
        {
            if (connection!.State != System.Data.ConnectionState.Open)
            {
                await connection.OpenAsync();
            }
            NpgsqlCommand cmd = (NpgsqlCommand) connection!.CreateCommand();
            cmd.CommandText = sql;
            if (parameters != null && parameters.Count > 0)
            {
                foreach(var parameter in parameters)
                {
                    cmd.Parameters.AddWithValue(parameter.Key, parameter.Value);
                }
            }
            return await cmd.ExecuteScalarAsync();
        }

        public override async Task<int> ExecuteQueryAsync(string sql, Dictionary<string, object> ? parameters = null)
        {
            if (connection!.State != System.Data.ConnectionState.Open)
            {
                await connection.OpenAsync();
            }
            NpgsqlCommand cmd = (NpgsqlCommand) connection!.CreateCommand();
            cmd.CommandText = sql;
            if (parameters != null && parameters.Count > 0)
            {
                foreach(var parameter in parameters)
                {
                    cmd.Parameters.AddWithValue(parameter.Key, parameter.Value);
                }
            }
            return await cmd.ExecuteNonQueryAsync();
        }

        public override async Task<bool> OpenAsync()
        {
            try { await connection?.OpenAsync()!; } catch { return false; }
            return true;
        }
        
        public override async Task<bool> CloseAsync()
        {
            try { await connection?.CloseAsync()!; } catch { return false; }
            return true;
        }
    }
}