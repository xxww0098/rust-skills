// Scene 12: SeaORM N+1 + SELECT *.
async fn list(db: &DatabaseConnection) -> Result<Vec<(Cake, Vec<Fruit>)>, DbErr> {
    let mut out = Vec::new();
    for cake in Cake::find().all(db).await? {
        let fruits = cake.find_related(Fruit).all(db).await?;
        out.push((cake, fruits));
    }
    Ok(out)
}
