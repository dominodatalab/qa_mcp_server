# QA MCP Server for Domino Data Science Platform

**Comprehensive UAT & Performance Testing via MCP Protocol**

Transform your Domino platform validation with AI-powered testing. This MCP server exposes **32 specialized tools** that enable LLMs to perform intelligent platform assessment, automated UAT workflows, and data-driven performance analysis.

## 🎯 **What This Unlocks**

**Ask your AI assistant:**
- *"Is our Domino platform ready for production?"*
- *"Can the system handle 50 concurrent data science jobs?"*  
- *"Why are users experiencing authentication issues?"*
- *"What's our baseline performance for ML model deployment?"*

**Get intelligent responses with:**
- ✅ Automated test execution across all platform features
- 📊 Performance metrics and capacity analysis  
- 🔍 Detailed diagnostics with actionable recommendations
- 🚀 One-command comprehensive UAT suites

---

## 🚀 **32 MCP Tools Available**

### **🔧 Core Job Execution (4 tools)**
Execute and monitor jobs with MLflow integration
```
run_domino_job | check_domino_job_run_status | check_domino_job_run_results | open_web_browser
```

### **🧪 UAT Testing Suite (12 tools)**  
Comprehensive platform feature validation
```
test_user_authentication | test_project_operations | test_job_execution
test_workspace_operations | test_environment_operations | test_dataset_operations  
test_file_management_operations | test_collaboration_features | test_model_operations
enhanced_test_dataset_operations | enhanced_test_model_operations | enhanced_test_advanced_job_operations
```

### **⚡ Performance Testing (5 tools)**
Load, stress, and capacity testing
```
performance_test_workspaces | performance_test_jobs | stress_test_api
performance_test_concurrent_jobs | performance_test_data_upload_throughput
```

### **🎯 Comprehensive Suites (6 tools)**
One-command complete assessments  
```
run_master_comprehensive_uat_suite ← ULTIMATE SUITE
run_comprehensive_advanced_uat_suite | run_admin_uat_suite | run_user_uat_suite
run_comprehensive_split_uat_suite | cleanup_test_resources
```

### **🛠️ Platform Management (5 tools)**
Project, dataset, and resource management
```
create_project_if_needed | test_dataset_creation_and_upload 
test_environment_and_hardware_operations | test_advanced_job_operations | enhanced_test_file_management
```

---

## 📋 **Setup**

### **1. Install Dependencies**
```bash
git clone <your-repo>
cd qa_mcp_server
uv pip install -e .
```

### **2. Configure Environment**
Create `.env` file:
```dotenv
DOMINO_API_KEY='your_api_key_here'
DOMINO_HOST='https://your-domino-instance.com'
```

### **3. Configure MCP in Cursor**
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "qa_mcp_server": {
      "command": "uv",
      "args": ["--directory", "/path/to/qa_mcp_server", "run", "domino_qa_mcp_server.py"]
    }
  }
}
```

### **4. Start Testing**
Ask your AI: *"Run a comprehensive UAT assessment of our Domino platform"*

---

## 💡 **Smart Capabilities**

**🔄 Intelligent Resource Management**
- Auto-generated unique names (timestamp + UUID)
- Automatic cleanup of test resources
- Graceful error handling and recovery

**📊 Performance Insights**  
- Concurrent job capacity testing (20+ parallel jobs)
- Data upload throughput analysis
- API stress testing (100+ requests/sec)
- Resource utilization monitoring

**🎯 Comprehensive Coverage**
- Authentication workflows → Model deployment  
- Infrastructure validation → User experience testing
- Admin operations → Data science workflows
- Performance baselines → Capacity planning

**🤖 LLM-Optimized Responses**
- Structured JSON with actionable insights
- Pass/fail scoring with improvement recommendations  
- Detailed metrics for performance analysis
- Natural language summaries for non-technical stakeholders

---

## 🚀 **Example Workflows**

**Platform Readiness Assessment:**
```
You: "Is our platform ready for 100 data scientists?"
AI: → Runs run_master_comprehensive_uat_suite()
Response: ✅ 85% overall readiness | ⚠️ Scale workspace resources | 📊 Baseline: 45 concurrent jobs
```

**Performance Investigation:**
```  
You: "Why are model deployments slow?"
AI: → Runs enhanced_test_model_operations() + performance_test_concurrent_jobs()
Response: 🔍 Model registry bottleneck detected | ⏱️ Avg deployment: 3.2min | 💡 Recommend compute upgrade
```

**Capacity Planning:**
```
You: "What's our current performance baseline?"
AI: → Runs performance testing suite
Response: 📊 20 concurrent jobs max | 🚀 85MB/s upload speed | 💾 65% resource utilization | 📈 Growth capacity: 40%
```

---

**Ready to transform your Domino platform validation?** Install the MCP server and let AI handle your UAT workflows!

**Tech Stack:** Python 3.11+ | FastMCP | python-domino v1.4.8 | Domino v6.1+ 