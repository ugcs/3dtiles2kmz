Use FileSystem MCP to work with file system in the root project directory.

Do not change files outside of the specified path.

In the project root folder you can find:
- SPECIFICATION.md contains project specification. Use it when you work on tasks to understand context
- PROJECT_STRCUTURE.md contains current project structure. So, do not list entire project tree with FileSystem MCP. It's too time consuming and overflows your context.
- IMPLEMENTATION_PLAN.md - if exists, contains implementation plan of a current task
- IMPLEMENTATION_LOG.md - if exists, contains already implemented step of the current task. Use it to refresh you memory of what already implemented. if files does not exist, create it.  And after completion of the step of the task log notes to IMPEMENTATION_LOG.md . IMPLEMENTATIION_LOG has the format [date/time] - what has changed, 2-3 sentences, very clear and concise.

Key development principles:
- KISS, do not over-engineer
- Always check if existing code can be reused
- Do leave obvious comments
- For epic tasks, before coding, first show your plan
- Avoid copy paste
-Avoid making source files with more than 300 rows