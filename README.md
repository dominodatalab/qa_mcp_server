# Domino UAT MCP Server

This project provides a comprehensive **User Acceptance Testing (UAT) MCP Server** for Domino Data Science Platform v6.1. When combined with AI tools like Cursor, it enables intelligent assessment of platform readiness, automated testing workflows, and data-driven validation of Domino deployments.

## 🎯 **Key Features**

- **27 UAT Functions**: Comprehensive testing coverage for all Domino Platform features
- **Smart Resource Management**: Enhanced functions with automatic cleanup and unique naming
- **Admin vs User Testing**: Clear separation between infrastructure and end-user validation
- **Performance Testing**: Load, concurrency, and stress testing capabilities
- **Intelligent Scoring**: Pass/fail thresholds with actionable recommendations
- **LLM-Optimized**: Designed for natural language interaction and automated testing

## 🚀 **Available UAT Functions**

### **Comprehensive Suites** (Recommended)
- `run_comprehensive_split_uat_suite()` - **Best for complete assessment**
- `run_admin_uat_suite()` - Infrastructure and administration testing
- `run_user_uat_suite()` - Data science workflow validation

### **Enhanced Smart Functions**
- `enhanced_test_dataset_operations()` - Dataset lifecycle with auto-cleanup
- `enhanced_test_model_operations()` - Model deployment with dummy creation
- `enhanced_test_file_management()` - File operations with multiple types
- `enhanced_test_advanced_job_operations()` - Job testing with hardware detection

### **Performance Testing**
- `performance_test_concurrent_jobs()` - Concurrent job capacity testing
- `performance_test_data_upload_throughput()` - Data upload performance
- `stress_test_api()` - API load and stability testing

*See `uat_test_scenarios.md` for complete function reference.*

## 🔧 **How it Works**

The enhanced `domino_qa_mcp_server.py` uses the `fastmcp` library and official `python-domino` v1.4.8 library to provide comprehensive UAT capabilities. It exposes 27 functions as MCP tools that LLMs can call to:

- **Assess platform readiness** with scored results and recommendations
- **Test user workflows** from authentication to model deployment
- **Validate infrastructure** including hardware tiers and environments
- **Perform load testing** with concurrent jobs and data uploads
- **Manage resources intelligently** with automatic cleanup

The server communicates via standard input/output with structured JSON responses containing detailed test results, scoring, and actionable recommendations.

## 📋 **Setup**

### Step 1: **Clone the Repository**
```bash
git clone https://github.com/domino-field/qa_mcp_server.git
cd qa_mcp_server
```

### Step 2: **Install Dependencies**
```bash
# Install using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### Step 3: **Configure Environment**
Create a `.env` file with your Domino credentials:
```dotenv
DOMINO_API_KEY='your_api_key_here'
DOMINO_HOST='https://your-domino-instance.com'
```

### Step 4: **Configure Cursor MCP**
Add to your `.cursor/mcp.json`:
```json
    {
    "mcpServers": {
        "domino_qa_server": {
            "command": "uv",
            "args": ["--directory", "/full/directory/path/to/qa_mcp_server", "run", "domino_qa_mcp_server.py"]
        }
      }
    }
```

## 🎯 **Usage Examples**

### **Complete Platform Assessment**
```
LLM Query: "Is our Domino platform ready for the data science team?"

Function Called: run_comprehensive_split_uat_suite("oussama", "test")

Response: 
✅ Admin UAT: 75% pass rate - Infrastructure ready
✅ User UAT: 83% pass rate - Workflows operational  
⚠️ Recommendations: Model deployment needs attention
```

### **Performance Investigation**
```
LLM Query: "Can the system handle 20 concurrent data science jobs?"

Function Called: performance_test_concurrent_jobs("oussama", "test", concurrent_count=20)

Response:
✅ 20 concurrent jobs completed successfully
⏱️ Average completion time: 45 seconds
📊 Resource utilization: 78% CPU, 65% memory
```

### **Feature-Specific Testing**
```
LLM Query: "Can users upload and work with large datasets?"

Function Called: enhanced_test_dataset_operations("oussama", "test")

Response:
✅ Dataset creation: Working
✅ Upload (100MB): 85MB/s throughput  
✅ Access and management: Operational
✅ Cleanup: Automatic removal successful
```

## 📊 **Test Categories & Scoring**

### **Admin UAT** (70% pass threshold)
- Infrastructure monitoring (25%)
- User management (20%) 
- System configuration (20%)
- Resource allocation (15%)
- Platform administration (20%)

### **User UAT** (75% pass threshold)
- Authentication workflows (20%)
- Development environments (25%)
- Data science workflows (25%) 
- Collaboration features (15%)
- Model deployment (15%)

## 🔍 **Smart Enhancements**

### **Automatic Resource Management**
- **Unique naming**: Timestamp + UUID prevents conflicts
- **Auto-cleanup**: Test resources automatically removed
- **Error recovery**: Graceful handling of failures
- **Resource tracking**: Comprehensive cleanup on completion

### **Enhanced Testing**
- **Multiple file types**: Python, CSV, JSON, images
- **Hardware detection**: Automatic tier selection and validation
- **Performance metrics**: Detailed timing and throughput analysis
- **Comprehensive validation**: End-to-end workflow testing

## ⚡ **Performance Capabilities**

- **Concurrent Workspaces**: Test up to 50+ simultaneous workspace startups
- **Parallel Jobs**: Execute 20+ concurrent compute jobs with monitoring
- **Data Throughput**: Upload performance testing with various file sizes
- **API Stress Testing**: High-concurrency API load testing (100+ requests/sec)
- **Resource Monitoring**: CPU, memory, and infrastructure utilization tracking

## 🤖 **LLM Integration**

The server is designed for natural language interaction. LLMs can ask questions like:

- *"Is the platform ready for production?"*
- *"Why are users having authentication issues?"*
- *"Can the system handle our expected data science workload?"*
- *"What's the current performance baseline?"*

The server responds with structured, actionable information including pass/fail status, detailed metrics, and specific recommendations.

## 📚 **Documentation**

- `uat_test_scenarios.md` - Complete function reference and usage patterns
- `domino_qa_mcp_server.py` - Enhanced MCP server implementation
- `test_updated_mcp_server.py` - Validation and testing scripts

## 🔗 **Requirements**

- **Python 3.8+**
- **Domino Data Science Platform v6.1+**
- **Valid Domino API credentials**
- **Network access to Domino instance**
- **Libraries**: `fastmcp`, `python-domino>=1.4.8`, `requests`, `python-dotenv`

---

**Ready to assess your Domino platform?** Start the MCP server and ask your AI assistant to run a comprehensive UAT assessment! 