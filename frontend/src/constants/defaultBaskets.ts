export interface DefaultBasket {
  id: string;
  name: string;
  description: string;
  tickers: string;
  icon: string;
}

export const DEFAULT_BASKETS: DefaultBasket[] = [
  {
    id: 'metals-mining',
    name: 'Metals & Mining',
    description: 'Global metals and mining companies across various commodities',
    tickers: '0976.HK,2899.HK,5713.T,AAL.L,AMG.AS,VAL.JO,ANTO.L,ARI.JO,BOL.ST,CAML.L,CLF,CMP,DRR.AX,FCX,FM.TO,HBM.TO,IGO.AX,ILU.AX,IMP.JO,IVN.TO,KGH.WA,LUN.TO,LYC.AX,MIN.AX,NPH.JO,NUE,PLS.AX,RIO.L,SCCO,SFR.AX,SQM,SYR.AX,TECK-B.TO,VALE,VALT.L',
    icon: '⛏️'
  }
];
