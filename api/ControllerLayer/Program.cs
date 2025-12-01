//using businesslayer
//using dataaccesslayer

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddOpenApi();
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
//builder.Services.AddDataAccessDependencies(builder.Configuration);
//builder.Services.AddServiceDependencies(builder.Configuration);

// Add CORS
builder.Services.AddCors(options =>
    {
        options.AddPolicy("AllowReactApp",
            policy =>
            {
                policy.WithOrigins("http://localhost:3000", "http://localhost:5173") // Add your React port here
                      .AllowAnyHeader()
                      .AllowAnyMethod();
            }
        );
    }
);

var app = builder.Build();

app.UseCors("AllowReactApp"); // Use CORS

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment()) {
    app.UseSwagger(opt=> opt.OpenApiVersion = Microsoft.OpenApi.OpenApiSpecVersion.OpenApi3_0);
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();