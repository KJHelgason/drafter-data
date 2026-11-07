import json,sys
src,out=sys.argv[1],sys.argv[2]
L=open(src,encoding='utf-8').read().split('\n')
E=L[0][3:].split('~');T=L[1][3:].split('~');C=L[2][3:].split('~')
RM={'B':'Bot','S':'Support','M':'Mid','J':'Jungle','T':'Top'}
def ch(s):return [C[int(s[i:i+2],36)] for i in range(0,10,2)]
rows=[]
for l in L[3:]:
    if not l.strip():continue
    f=l.split('|')
    ev=E[int(f[0],36)];p=f[1];patch='26.20' if p=='2' else '26.'+p
    r={'OverviewPage':ev,'GameId':ev+'_'+f[2],'Patch':patch,'Team1':T[int(f[3],36)],'Team2':T[int(f[4],36)],'Winner':int(f[5])}
    for t,(pk,ro,bn) in zip((1,2),((f[6],f[7],f[8]),(f[9],f[10],f[11]))):
        P=ch(pk);B=ch(bn)
        for i in range(5):
            r[f'Team{t}Pick{i+1}']=P[i];r[f'Team{t}Role{i+1}']=RM[ro[i]];r[f'Team{t}Ban{i+1}']=None if B[i] in('None','-') else B[i]
    rows.append(r)
json.dump({'source':'Leaguepedia Cargo (Special:CargoExport) PicksAndBansS7 joined with ScoreboardGames on GameId for Patch','fetched_at':'2026-11-06','note':'Team1 = blue side. Pick order B1 R1 R2 B2 B3 R3 R4 B4 B5 R5 = Team1Pick1, Team2Pick1-2, Team1Pick2-3, Team2Pick3, Team2Pick4, Team1Pick4-5, Team2Pick5. Patch 26.x = gol.gg 16.x. Unplayed placeholder rows dropped.','events':sorted(set(r['OverviewPage'] for r in rows)),'games':len(rows),'rows':rows},open(out,'w',encoding='utf-8'),ensure_ascii=False,indent=0)
print(len(rows))
