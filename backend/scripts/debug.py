from ortools.sat.python import cp_model

# %%
model = cp_model.CpModel()
x = model.NewBoolVar('x')
model.Minimize(x)
solver = cp_model.CpSolver()
status = solver.Solve(model)
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print("ok")
    print(status)
# %%
