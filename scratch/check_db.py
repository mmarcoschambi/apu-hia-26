import optuna

def check_db():
    try:
        study = optuna.load_study(study_name='s4_main_v2', storage='sqlite:///outputs/optuna_s4/s4_main_v2.db')
        for t in study.trials[-5:]:
            print(f"Trial {t.number}: state={t.state.name}, trades={t.user_attrs.get('trades')}, calmar={t.user_attrs.get('calmar')}, cagr={t.user_attrs.get('cagr')}")
    except Exception as e:
        print(f"Error: {e}")

check_db()
