/* Independent geometric check classification for experimental report variants.
   It neither evaluates nor sorts moves. Coordinates follow engine.decode(). */
static void read_board(int b[64]) {
 memset(b,0,64*sizeof(int));
 for(unsigned side=0;side<2;side++){
  unsigned base=side?07000:03000;int sign=side?-1:1;
  for(unsigned half=0;half<2;half++)for(unsigned bit=0;bit<32;bit++)
   if(M[base+2+half]&(1ULL<<bit))b[63-(bit+32*(1-half))]=sign;
  for(unsigned off=016;off<=036;off+=2){uint64_t w=M[base+off];unsigned co=(w>>36)&0177,k=(w>>32)&7;
   if(!(w&(1ULL<<35))&&co<64){int p=k==3?2:k==4?3:k==5?4:k==6?5:k==7?6:0;b[63-co]=sign*p;}
  }
 }
}
static int attacked(const int b[64],unsigned side) {
 int king=-1,own=side?-6:6;
 for(int i=0;i<64;i++)if(b[i]==own){king=i;break;}
 if(king<0)return 0;
 int kf=king%8,kr=king/8;
 for(int i=0;i<64;i++){
  int p=b[i];if(!p||((p<0)==side))continue;
  int f=i%8,r=i/8,df=kf-f,dr=kr-r,t=p<0?-p:p,af=df<0?-df:df,ar=dr<0?-dr:dr;
  if(t==1){if(af==1&&dr==(p>0?1:-1))return 1;continue;}
  if(t==2){if((af==1&&ar==2)||(af==2&&ar==1))return 1;continue;}
  if(t==6){if(af<=1&&ar<=1)return 1;continue;}
  int diag=af==ar,straight=df==0||dr==0;
  if(!((t==3&&diag)||(t==4&&straight)||(t==5&&(diag||straight))))continue;
  int sf=(df>0)-(df<0),sr=(dr>0)-(dr<0),ff=f+sf,rr=r+sr,blocked=0;
  while(ff!=kf||rr!=kr){if(b[rr*8+ff]){blocked=1;break;}ff+=sf;rr+=sr;}
  if(!blocked)return 1;
 }
 return 0;
}
static int report_board_check(unsigned side){int b[64];read_board(b);return attacked(b,side);}
static void classify_candidate(uint64_t word,unsigned side,int *capture,int *check,int *incheck,int *material_after){
 static const int values[7]={0,32,112,112,160,320,512};
 int b[64];read_board(b);*incheck=attacked(b,side);
 unsigned kind=(word>>12)&037,dstcode=(word>>36)&077;int dst=63-dstcode,src=-1;
 if(kind<020){unsigned base=side?07000:03000;src=63-((M[base+014+2*kind]>>36)&077);}
 else if(kind<036){int delta=kind==025||kind==030||kind==032?9:kind==026||kind==031||kind==033?7:kind==035?16:8;src=63-(dstcode+(side?-delta:delta));}
 else{src=side?60:4;dst=(side?56:0)+(kind==036?6:2);}
 int piece=b[src];*capture=b[dst]!=0;
 if((piece==1||piece==-1)&&src%8!=dst%8&&!b[dst]){*capture=1;b[dst+(side?8:-8)]=0;}
 b[dst]=piece;b[src]=0;
 if(kind>=020&&kind<030)b[dst]=side?-5:5;
 if(kind>=036){int row=side?56:0,rf=row+(kind==036?7:0),rt=row+(kind==036?5:3);b[rt]=b[rf];b[rf]=0;}
 *check=attacked(b,1-side);int sum=0;
 for(int i=0;i<64;i++){int p=b[i];sum+=(p<0?-1:1)*values[p<0?-p:p];}
 *material_after=1024+(side?-sum:sum);
}
