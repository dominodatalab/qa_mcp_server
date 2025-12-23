# QA MCP Server for Domino Data Science Platform

**Comprehensive UAT & Performance Testing via MCP Protocol**

Transform your Domino platform validation with AI-powered testing. This MCP server exposes **24 specialized tools** and **2 standardized prompts** that enable LLMs to perform intelligent platform assessment, automated UAT workflows, and data-driven performance analysis.

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

## 🚀 **24 MCP Tools Available**

### **🔧 Core Job Execution (4 tools)**
Execute and monitor jobs with MLflow integration
```
run_domino_job | check_domino_job_run_status | check_domino_job_run_results | open_web_browser
```

### **🧪 End-to-End UAT Suite (14 tools)**
These are the 14 tests executed in the `end_to_end_uat_protocol`:
```
1. test_post_upgrade_env_rebuild - Environment build validation
2. test_file_management_operations - File operations
3. test_file_version_reversion - File version reversion
4. test_project_copying - Project copying
5. test_project_forking - Project forking
6. test_advanced_job_operations - Job operations
7. test_job_scheduling - Job scheduling
8. test_comprehensive_ide_workspace_suite - Workspace IDEs
9. test_workspace_file_sync - Workspace file sync
10. test_workspace_hardware_tiers - Hardware tiers
11. enhanced_test_dataset_operations - Dataset operations
12. test_model_api_publish - Model API publish
13. test_app_publish - App publish
14. run_admin_portal_uat_suite - Admin portal
```

### **⚡ Performance Testing (3 tools)**
Load, stress, and capacity testing
```
performance_test_concurrent_jobs | performance_test_data_upload_throughput | performance_test_parallel_workspaces
```

### **🧹 Cleanup Tools (2 tools)**
Remove test resources after UAT execution
```
cleanup_all_project_workspaces | cleanup_all_project_datasets
```

### **🔐 Authentication (1 tool)**
User access verification
```
test_user_authentication
```

---

## 📝 **MCP Prompts (2 Standardized Workflows)**

**Prompts** are pre-configured workflows that guide the LLM through structured testing sequences. The LLM client reads credentials from `@domino_project_settings.md` and provides them as parameters.

### **Prompt 1: `quick_auth_test`**

**Purpose:** Quick user authentication verification

**Parameters:**
- `user_name`: Domino username (from @domino_project_settings.md)
- `project_name`: Domino project name (from @domino_project_settings.md)

**What it does:**
1. Executes the `test_user_authentication` tool
2. Verifies platform access with provided credentials
3. Returns authentication status report

**Typical use case:** First test to verify credentials work before running comprehensive suites

---

### **Prompt 2: `end_to_end_uat_protocol`**

**Purpose:** Comprehensive 14-test UAT suite with strict continuous execution

**Parameters:**
- `user_name`: Domino username (from @domino_project_settings.md)
- `project_name`: Domino project name (from @domino_project_settings.md)

**Mandatory Test Sequence (Execute in this exact order):**

1. **test_post_upgrade_env_rebuild** - Environment build validation
2. **test_file_management_operations** - File operations (upload, download, move, rename)
3. **test_file_version_reversion** - File version control and reversion
4. **test_project_copying** - Project copying functionality
5. **test_project_forking** - Project forking functionality
6. **test_advanced_job_operations** - Advanced job operations
7. **test_job_scheduling** - Job scheduling workflows
8. **test_comprehensive_ide_workspace_suite** - All workspace IDEs (Jupyter, RStudio, VSCode)
9. **test_workspace_file_sync** - Workspace file synchronization
10. **test_workspace_hardware_tiers** - Hardware tier validation (small-k8s, medium-k8s, large-k8s)
11. **enhanced_test_dataset_operations** - Enhanced dataset operations
12. **test_model_api_publish** - Model API publishing
13. **test_app_publish** - Application publishing
14. **run_admin_portal_uat_suite** - Admin portal comprehensive validation

**Cleanup Phase (Executes after Test 14):**
- `cleanup_all_project_workspaces` - Removes all test workspaces
- `cleanup_all_project_datasets` - Removes all test datasets

**Final Report:** Comprehensive summary table with pass/fail status and recommendations

**⚠️ Strict Execution Rules:**
- ✅ Continuous execution (no pauses between tests)
- ✅ No user confirmation requests during execution
- ✅ Cleanup only after all 14 tests complete
- ✅ Single comprehensive report at end
- ❌ Do NOT stop or ask for input between tests

### **Using Prompts**

1. **Create Configuration File** (`domino-qa/domino_project_settings.md`):
```markdown
USER_NAME = "your-username"
PROJECT_NAME = "your-project-name"
```

2. **Invoke Prompt in LLM Client**:
```
"Run the quick_auth_test prompt with my credentials from @domino_project_settings.md"
```
or
```
"Execute the end_to_end_uat_protocol using settings from @domino_project_settings.md"
```

The LLM client will:
- Read `@domino_project_settings.md`
- Extract USER_NAME and PROJECT_NAME
- Invoke the prompt with these parameters
- Execute the guided workflow

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