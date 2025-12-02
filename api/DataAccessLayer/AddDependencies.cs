using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using DataAccessLayer.DbContext;
using DataAccessLayer.Repositories;

namespace DataAccessLayer
{
    public static class AddDependecies
    {
        public static IServiceCollection AddDataAccessDependencies(this IServiceCollection services, IConfiguration configuration)
        {
            services.AddScoped<DatabaseContext> (options =>
            {
                String ? connectionString = configuration.GetConnectionString("WebApiDatabase");
                if (!string.IsNullOrWhiteSpace(connectionString))
                {
                    return new PgDatabaseContext(connectionString);
                }
                throw new Exception(connectionString);
            });
            services.AddScoped<IEmployeeRepository, EmployeeRepository> ();
            //services.AddScoped<IDepartmentRepository, DepartmentRepository> ();
            return services;
        }
    }
}