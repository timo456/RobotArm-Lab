# Publishing checklist (user-controlled)

This delivery creates local Git history only. No remote, push or public publishing
was performed. Review README, license ownership, reports and generated media first.

1. Run the README verification commands and review `git status` and `git diff`.
2. Confirm no `.venv`, caches, logs, credentials, private paths or private model data
   are tracked. `.gitignore` excludes local runtime output; only reviewed evidence
   belongs under `reports/` and `docs/media/`.
3. Create an empty repository named `RobotArm-Lab` in your GitHub account when ready.
4. After replacing `YOUR_ACCOUNT`, run these commands yourself:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/RobotArm-Lab.git
git push -u origin main
```

5. Inspect both GitHub Actions jobs. Remote CI is untested until those actual runs
   complete. Set branch protection and require the workflow if desired.
6. Add repository topics (`robotics`, `kinematics`, `trajectory-planning`, `pybullet`),
   a description and README demo. Create a release only after the checks pass.

Do not describe this project as a certified safety system or a hardware-ready driver.
