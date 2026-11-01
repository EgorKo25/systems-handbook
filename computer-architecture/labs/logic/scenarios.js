/* Original bounded teaching scenes, not a second full CPU, cycle or coherence simulator. */
(function(root,factory){'use strict';const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.M32Scenes=api;}(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const clone=x=>JSON.parse(JSON.stringify(x));
const unsigned=n=>Number.isInteger(n)&&n>=0&&n<=0xffffffff;
const sx=(n,bits)=>n>=2**(bits-1)?n-2**bits:n;
function jalrTarget(source,immediate=0){if(!unsigned(source)||!Number.isInteger(immediate)||immediate< -2048||immediate>2047)throw new Error('invalid-jalr-input');return ((((source+immediate)>>>0)&0xfffffffe)>>>0);}
function predictorStep(state,taken,{pc=0x1108,target=0x1104,btbTarget=0x1104}={}){
  if(!Number.isInteger(state)||state<0||state>3||typeof taken!=='boolean'||![pc,target].every(unsigned)||(btbTarget!==null&&!unsigned(btbTarget)))throw new Error('invalid-predictor-input');
  const predictsTaken=state>=2,predictedPC=predictsTaken?btbTarget:(pc+4)>>>0,actualPC=taken?target:(pc+4)>>>0;
  return {stateBefore:state,predictsTaken,btbTarget,predictedPC,taken,actualPC,predictionAvailable:predictedPC!==null,directionCorrect:predictsTaken===taken,addressCorrect:predictedPC===actualPC,mispredict:predictedPC!==null&&predictedPC!==actualPC,stateAfter:Math.max(0,Math.min(3,state+(taken?1:-1)))};
}
function predictorTrace(initial=1,btbTarget=0x1104){let state=initial;return [true,true,false].map(taken=>{const row=predictorStep(state,taken,{btbTarget});state=row.stateAfter;return row;});}
function renameTrace({faultA=false,input=42}={}){
  if(typeof faultA!=='boolean'||!unsigned(input))throw new Error('invalid-rename-input');
  const state={rat:{x5:'P1',x6:'P2',x8:'P3'},committed:{x5:'P1',x6:'P2',x8:'P3'},physical:{P0:{ready:true,value:0},P1:{ready:true,value:0x2000},P2:{ready:true,value:99},P3:{ready:true,value:0}},free:['P10','P11','P12','P13'],rob:[],store:null,memory2200:0,otherCoreObserved:null};
  const trace=[],record=(event)=>trace.push({event,...clone(state)});
  const allocate=(label,rd,sources)=>{const sourcePhysical=sources.map(name=>name==='x0'?'P0':state.rat[name]);const dest=rd?state.free.shift():null;if(rd&&!dest)throw new Error('no-free-register');const stale=rd?state.rat[rd]:null;if(rd){state.rat[rd]=dest;state.physical[dest]={ready:false,value:null};}state.rob.push({label,rd,sources:sourcePhysical,dest,stale,ready:false,fault:null});record('rename '+label);};
  const entry=label=>state.rob.find(row=>row.label===label);
  const complete=(label,value)=>{const row=entry(label);if(!row.sources.every(name=>state.physical[name].ready))throw new Error('source-not-ready');if(row.dest)state.physical[row.dest]={ready:true,value:value>>>0};row.ready=true;record('execute '+label);};
  const commit=()=>{const row=state.rob[0];if(!row||!row.ready||row.fault)throw new Error('head-not-committable');if(row.rd){state.committed[row.rd]=row.dest;state.free.push(row.stale);}else state.store.committed=true;state.rob.shift();record('commit '+row.label);};
  record('initial');allocate('A','x6',['x5']);allocate('B','x8',['x0']);allocate('C','x6',['x6']);allocate('D',null,['x5','x6']);complete('B',7);
  if(faultA){entry('A').fault='access-fault';record('fault A');const reclaimed=state.rob.filter(row=>row.dest).map(row=>row.dest);state.rat={...state.committed};state.rob=[];state.store=null;for(const name of reclaimed){state.physical[name]={ready:false,value:null};if(!state.free.includes(name))state.free.push(name);}record('rollback before A');return trace;}
  complete('A',input);complete('C',(input+1)>>>0);const d=entry('D'),value=state.physical[d.sources[1]].value;state.store={address:0x2200,width:4,bytes:[value&255,value>>>8&255,value>>>16&255,value>>>24&255],value,committed:false};complete('D',null);commit();commit();commit();commit();
  state.memory2200=state.store.value;state.store=null;record('drain to model memory; observer unspecified');return trace;
}
function decodeControl(word){
  if(!unsigned(word))throw new Error('invalid-word');
  const opcode=word&127,rd=word>>>7&31,rs1=word>>>15&31,rs2=word>>>20&31,funct3=word>>>12&7;
  if(opcode===0x13&&funct3===0)return {op:'ADDI',rd,rs1,imm:sx(word>>>20,12)};
  if(opcode===3&&funct3===2)return {op:'LW',rd,rs1,imm:sx(word>>>20,12)};
  if(opcode===0x23&&funct3===2)return {op:'SW',rs1,rs2,imm:sx((word>>>25)*32+(word>>>7&31),12)};
  if(opcode===0x63&&funct3===1){const raw=(word>>>31)*4096+(word>>>7&1)*2048+(word>>>25&63)*32+(word>>>8&15)*2;return {op:'BNE',rs1,rs2,imm:sx(raw,13)};}
  if(opcode===0x6f){const raw=(word>>>31)*1048576+(word>>>12&255)*4096+(word>>>20&1)*2048+(word>>>21&1023)*2;return {op:'JAL',rd,imm:sx(raw,21)};}
  if(opcode===0x67&&funct3===0)return {op:'JALR',rd,rs1,imm:sx(word>>>20,12)};
  throw new Error('unsupported-control-word');
}
const LOOP=Object.freeze({0x1100:0x00300393,0x1104:0xfff38393,0x1108:0xfe039ee3});
const CALL=Object.freeze({0x1100:0x100000ef,0x1200:0xff010113,0x1204:0x00112623,0x1208:0x00000013,0x120c:0x0f4000ef,0x1300:0x00008067,0x1210:0x00c12083,0x1214:0x01010113,0x1218:0x00008067});
function controlTrace(scene,{loopCount=3,restoreLink=true,initialSP=0x7000,limit=64}={}){
  if(!['loop','call'].includes(scene)||!Number.isInteger(loopCount)||loopCount<1||loopCount>10||typeof restoreLink!=='boolean'||!unsigned(initialSP)||!Number.isInteger(limit)||limit<1||limit>128)throw new Error('invalid-control-scene');
  const program={...(scene==='loop'?LOOP:CALL)};if(scene==='loop')program[0x1100]=((loopCount<<20)|0x393)>>>0;else if(!restoreLink)program[0x1210]=0x00000013;
  const regs=new Uint32Array(32),memory={};regs[2]=initialSP;let pc=0x1100,status='limit',cause=null;const trace=[];
  function wordAccess(address){if(!unsigned(address)||address<0x6000||address>0x6ffc)throw new Error('outside-scene-stack');if(address%4)throw new Error('misaligned-scene-stack');}
  for(let n=0;n<limit;n++){
    if((scene==='loop'&&pc===0x110c)||(scene==='call'&&pc===0x1104)){status='scene-goal';break;}
    if(pc%4||program[pc]===undefined){status='trap';cause=pc%4?'instruction-address-misaligned':'outside-scene-code';break;}
    const word=program[pc],d=decodeControl(word),before={pc,ra:regs[1],sp:regs[2],x7:regs[7]},row={word,decoded:d,before,memory:null};let next=(pc+4)>>>0,value,address;
    try{
      if(d.op==='ADDI')value=(regs[d.rs1]+d.imm)>>>0;
      if(d.op==='BNE'){row.taken=regs[d.rs1]!==regs[d.rs2];if(row.taken)next=(pc+d.imm)>>>0;}
      if(d.op==='JAL'){value=next;next=(pc+d.imm)>>>0;}
      if(d.op==='JALR'){value=next;next=jalrTarget(regs[d.rs1],d.imm);}
      if(next%4)throw new Error('instruction-address-misaligned');
      if(d.op==='LW'){address=(regs[d.rs1]+d.imm)>>>0;wordAccess(address);if([0,1,2,3].some(i=>memory[address+i]===undefined))throw new Error('uninitialised-scene-stack');value=(memory[address]+memory[address+1]*256+memory[address+2]*65536+memory[address+3]*16777216)>>>0;row.memory={kind:'read',address,bytes:[0,1,2,3].map(i=>memory[address+i])};}
      if(d.op==='SW'){address=(regs[d.rs1]+d.imm)>>>0;wordAccess(address);const data=regs[d.rs2];for(let i=0;i<4;i++)memory[address+i]=data>>>8*i&255;row.memory={kind:'write',address,bytes:[0,1,2,3].map(i=>memory[address+i])};}
      if(d.rd&&value!==undefined)regs[d.rd]=value;regs[0]=0;pc=next;row.after={pc,ra:regs[1],sp:regs[2],x7:regs[7]};trace.push(row);
      if(scene==='call'&&before.pc===0x1218&&pc!==0x1104){status='wrong-return';cause='saved-link-not-restored';break;}
    }catch(error){status='trap';cause=error.message;row.after={...before};row.fault=cause;trace.push(row);break;}
  }
  if(status==='limit'&&((scene==='loop'&&pc===0x110c)||(scene==='call'&&pc===0x1104)))status='scene-goal';
  return {scene,status,cause,pc,regs:Array.from(regs),memory,trace,stepMeaning:'one bounded instruction event, not a CPU cycle',program};
}
return Object.freeze({predictorStep,predictorTrace,renameTrace,decodeControl,controlTrace,jalrTarget,LOOP,CALL});
}));
