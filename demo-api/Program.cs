using System.Diagnostics;
using System.Diagnostics.Metrics;
using OpenTelemetry.Exporter;
using OpenTelemetry.Resources;
using OpenTelemetry.Metrics;
using OpenTelemetry.Logs;
using OpenTelemetry.Trace;

const string DemoApiActivitySourceName = "DemoApi";
using var demoApiActivitySource = new ActivitySource(DemoApiActivitySourceName);
using var demoApiMeter = new Meter(DemoApiActivitySourceName);
var businessOperations = demoApiMeter.CreateCounter<long>("demo.business.operations");

if (args.Contains("--healthcheck", StringComparer.Ordinal))
{
    using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
    try
    {
        using var response = await client.GetAsync("http://127.0.0.1:8080/healthz");
        Environment.ExitCode = response.IsSuccessStatusCode ? 0 : 1;
    }
    catch
    {
        Environment.ExitCode = 1;
    }
    return;
}

var builder = WebApplication.CreateBuilder(args);
var otlpEndpoint = builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://alloy:4317";

// Keep console output for local debugging. Only the OTLP path is ingested by Loki.
builder.Logging.ClearProviders();
// ASP.NET Core request-start logs can contain raw query strings.
builder.Logging.AddFilter("Microsoft.AspNetCore", LogLevel.Warning);
builder.Logging.AddJsonConsole(options =>
{
    options.IncludeScopes = true;
    options.TimestampFormat = "yyyy-MM-dd'T'HH:mm:ss.fff'Z'";
    options.UseUtcTimestamp = true;
});

// Preserve readable log bodies as well as typed OTLP attributes.
builder.Services.Configure<OpenTelemetryLoggerOptions>(options =>
    options.IncludeFormattedMessage = true);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(serviceName: "demo-api")
        .AddAttributes(new[]
        {
            new KeyValuePair<string, object>("deployment.environment.name", "lab")
        }))
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddMeter(DemoApiActivitySourceName)
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = new Uri(otlpEndpoint);
        }))
    .WithLogging(logging => logging
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = new Uri(otlpEndpoint);
        }))
    .WithTracing(tracing => tracing
        .AddSource(DemoApiActivitySourceName)
        .AddAspNetCoreInstrumentation(options =>
        {
            options.EnrichWithHttpResponse = (activity, _) =>
            {
                // Route templates are enough; drop potentially identifying request details.
                activity.SetTag("url.query", null);
                activity.SetTag("url.path", null);
                activity.SetTag("user_agent.original", null);
            };
        })
        .AddOtlpExporter(options =>
        {
            options.Protocol = OtlpExportProtocol.Grpc;
            options.Endpoint = new Uri(otlpEndpoint);
        }));

var app = builder.Build();
var loggerFactory = app.Services.GetRequiredService<ILoggerFactory>();
var requestLogger = loggerFactory.CreateLogger("DemoApi.Requests");
var businessLogger = loggerFactory.CreateLogger("DemoApi.Business");
var jobLogger = loggerFactory.CreateLogger("DemoApi.Jobs");

app.Use(async (context, next) =>
{
    var route = context.Request.Path.Value switch
    {
        "/ok" => "/ok",
        "/slow" => "/slow",
        "/error" => "/error",
        "/business-failure" => "/business-failure",
        "/jobs/run" => "/jobs/run",
        _ => null
    };

    if (route is null)
    {
        await next(context);
        return;
    }

    var stopwatch = Stopwatch.StartNew();
    try
    {
        await next(context);
    }
    finally
    {
        stopwatch.Stop();
        requestLogger.Log(
            context.Response.StatusCode >= StatusCodes.Status500InternalServerError
                ? LogLevel.Error
                : LogLevel.Information,
            new EventId(1001, "request_completed"),
            "request_completed event_name={event_name} http_route={http_route} http_response_status_code={http_response_status_code} duration_ms={duration_ms}",
            "request_completed",
            route,
            context.Response.StatusCode,
            stopwatch.Elapsed.TotalMilliseconds);
    }
});

app.MapGet("/ok", () =>
    Results.Ok(new { message = "OK" }));

app.MapGet("/slow", async () =>
{
    var delayMs = Random.Shared.Next(300, 1501);
    var validationDelayMs = Math.Max(1, delayMs / 5);
    var responseDelayMs = Math.Max(1, delayMs / 10);
    var workDelayMs = delayMs - validationDelayMs - responseDelayMs;

    using (demoApiActivitySource.StartActivity("ValidateRequest"))
    {
        await Task.Delay(validationDelayMs);
    }

    using (demoApiActivitySource.StartActivity("SimulatedWork"))
    {
        await Task.Delay(workDelayMs);
    }

    using (demoApiActivitySource.StartActivity("BuildResponse"))
    {
        await Task.Delay(responseDelayMs);
    }

    return Results.Ok(new
    {
        message = "Completed after a delay",
        delayMs
    });
});

app.MapGet("/error", () =>
    Results.Json(
        new { message = "A deterministic demo error occurred" },
        statusCode: StatusCodes.Status500InternalServerError));

// Deliberate business failure without an HTTP error.
app.MapGet("/business-failure", () =>
{
    using var span = demoApiActivitySource.StartActivity("SyntheticBusinessOperation");
    span?.SetTag("business.outcome", "failed");
    span?.SetTag("business.operation", "synthetic");
    span?.SetStatus(ActivityStatusCode.Error, "synthetic business failure");

    businessOperations.Add(1, new KeyValuePair<string, object?>("business_outcome", "failed"));
    businessLogger.LogWarning(
        "business_operation_completed event_name={event_name} business_outcome={business_outcome}",
        "business_operation_completed", "failed");

    return Results.Ok(new { status = "failed", businessOutcome = "failed" });
});

// A manually triggered ThreadPool job, deliberately awaited: not a durable queue.
app.MapPost("/jobs/run", async () =>
{
    await Task.Run(async () =>
    {
        using var span = demoApiActivitySource.StartActivity("SyntheticBackgroundJob");
        span?.SetTag("job.kind", "synthetic");
        await Task.Delay(25);
        jobLogger.LogInformation(
            "background_job_completed event_name={event_name} job_kind={job_kind} job_outcome={job_outcome}",
            "background_job_completed", "synthetic", "completed");
    });

    return Results.Ok(new { status = "completed" });
});

app.MapGet("/healthz", () =>
    Results.Ok(new { status = "healthy" }));

app.Run();
