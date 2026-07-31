import optuna

def main():
    try:
        study = optuna.load_study(study_name='s4_main_v2', storage='sqlite:///outputs/optuna_s4/s4_main_v2.db')
        trials = [t for t in study.trials if t.value is not None and t.value > 0]
        trials.sort(key=lambda t: t.value, reverse=True)
        
        print(f"Total valid trials > 0: {len(trials)}")
        print('--- TOP 3 TRIALS S4_MAIN_V2 ---')
        for i, t in enumerate(trials[:3]):
            print(f'\nRank {i+1} (Trial {t.number})')
            print(f'Score: {t.value:.4f}')
            print(f'Trades: {t.user_attrs.get("trades")}')
            print(f'Sharpe: {t.user_attrs.get("sharpe_raw")}')
            print(f'PF: {t.user_attrs.get("pf")}')
            print(f'MDD: {t.user_attrs.get("mdd")}')
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
