"""Quick DB inspection script."""
import asyncio
import sys
sys.path.insert(0, ".")


async def main() -> None:
    from memory.patient_repository import PatientRepository  # type: ignore
    repo = PatientRepository()
    await repo.create_tables()
    patients = await repo.get_all_patients()
    for p in patients:
        print(
            f"phone={p['phone']} name={p['name']} "
            f"lang={p['preferred_language']} "
            f"bookings={p['total_bookings']} "
            f"history_len={len(p.get('booking_history', []))}"
        )


asyncio.run(main())
